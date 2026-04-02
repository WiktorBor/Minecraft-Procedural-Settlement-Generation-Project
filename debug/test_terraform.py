"""
test_terraform.py
-----------------
Standalone test script for terraforming and terrain-clearing methods.

Connects to Minecraft, finds your player position automatically, and runs
the selected operation on the terrain around you.

Usage
-----
    python3 debug/test_terraform.py                        # terraform_area
    python3 debug/test_terraform.py --op lava
    python3 debug/test_terraform.py --op sparse
    python3 debug/test_terraform.py --op perimeter
    python3 debug/test_terraform.py --op all
    python3 debug/test_terraform.py --radius 48
    python3 debug/test_terraform.py --dry-run

Requirements
------------
Minecraft must be running with the GDMC HTTP mod.
Run from the project root.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, maximum_filter, minimum_filter

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_terraform")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Test terraforming methods around the player's position."
    )
    p.add_argument(
        "--op",
        choices=["terraform", "lava", "sparse", "perimeter", "all"],
        default="terraform",
        help=(
            "  terraform  — smooth bumps downward\n"
            "  lava       — clear surface lava pools\n"
            "  sparse     — remove isolated terrain clusters\n"
            "  perimeter  — level the build-area perimeter\n"
            "  all        — run all in pipeline order\n"
            "(default: terraform)"
        ),
    )
    p.add_argument(
        "--radius", type=int, default=64,
        help="Half-size of the test area centred on the player (default: 64).",
    )
    p.add_argument(
        "--passes", type=int, default=3,
        help="Smoothing passes for terraform_area (default: 3).",
    )
    p.add_argument(
        "--smooth-radius", type=int, default=3,
        help="Neighbourhood radius for terraform_area (default: 3).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be placed without touching the world.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# WorldAnalysisResult builder
# ---------------------------------------------------------------------------

def _build_analysis(editor, x_from: int, z_from: int, x_to: int, z_to: int):
    from gdpc import WorldSlice
    from gdpc.vector_tools import Rect
    from data.build_area import BuildArea
    from data.analysis_results import WorldAnalysisResult

    width = x_to - x_from + 1
    depth = z_to - z_from + 1

    logger.info(
        "Fetching world slice  x=[%d, %d]  z=[%d, %d]  (%d x %d blocks)...",
        x_from, x_to, z_from, z_to, width, depth,
    )

    rect = Rect((x_from, z_from), (width, depth))
    ws   = WorldSlice(rect)

    hg = np.array(ws.heightmaps["MOTION_BLOCKING_NO_LEAVES"]).T.astype(np.int32)
    hs = np.array(ws.heightmaps["MOTION_BLOCKING"]).T.astype(np.int32)
    ho = np.array(ws.heightmaps["OCEAN_FLOOR"]).T.astype(np.int32)

    hg = hg[:width, :depth]
    hs = hs[:width, :depth]
    ho = ho[:width, :depth]

    water_mask      = (hg > ho).astype(bool)
    water_distances = distance_transform_edt(~water_mask).astype(np.float32)

    gx, gz    = np.gradient(hg.astype(np.float32))
    slope_map = np.sqrt(gx ** 2 + gz ** 2).astype(np.float32)

    roughness_map = (
        maximum_filter(hg.astype(np.float32), size=11) -
        minimum_filter(hg.astype(np.float32), size=11)
    ).astype(np.float32)

    surface_blocks = np.full((width, depth), "minecraft:grass_block", dtype=object)
    scores         = np.ones((width, depth),  dtype=np.float32)
    biomes         = np.zeros((width, depth), dtype=np.int32)

    y_min = max(0,   int(hg.min()) - 5)
    y_max = min(320, int(hs.max()) + 10)

    area = BuildArea(
        x_from=x_from, y_from=y_min, z_from=z_from,
        x_to=x_to,     y_to=y_max,   z_to=z_to,
    )

    logger.info(
        "Heightmap ready -- min: %d  max: %d  mean: %.1f  std: %.1f",
        int(hg.min()), int(hg.max()), float(hg.mean()), float(hg.std()),
    )

    return WorldAnalysisResult(
        best_area             = area,
        surface_blocks        = surface_blocks,
        heightmap_ground      = hg,
        heightmap_surface     = hs,
        heightmap_ocean_floor = ho,
        roughness_map         = roughness_map,
        slope_map             = slope_map,
        water_mask            = water_mask,
        biomes                = biomes,
        scores                = scores,
        water_distances       = water_distances,
    )


# ---------------------------------------------------------------------------
# Player position
# ---------------------------------------------------------------------------

def _get_player_pos(editor) -> tuple[int, int, int]:
    import requests

    # Strategy 1: HTTP /players with NBT data
    try:
        resp = requests.get(
            "http://localhost:9000/players?includeData=true", timeout=3
        )
        if resp.ok:
            players = resp.json()
            if players:
                data_str = players[0].get("data", "")
                match = re.search(
                    r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]", data_str
                )
                if match:
                    px = int(float(match.group(1)))
                    py = int(float(match.group(2)))
                    pz = int(float(match.group(3)))
                    logger.info("Player position from /players: (%d, %d, %d)", px, py, pz)
                    return px, py, pz
    except Exception as e:
        logger.debug("HTTP /players failed: %s", e)

    # Strategy 2: editor.getPlayerPos()
    try:
        pos = editor.getPlayerPos()
        return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayerPos() failed: %s", e)

    # Strategy 3: editor.getPlayers()
    try:
        players = editor.getPlayers()
        if players:
            pos = players[0].pos
            return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayers() failed: %s", e)

    # Fallback: build area centre
    logger.warning("Could not locate player — using build area centre.")
    ba = editor.getBuildArea()
    cx = ba.offset.x + ba.size.x // 2
    cz = ba.offset.z + ba.size.z // 2
    return cx, 64, cz


# ---------------------------------------------------------------------------
# Dry-run editor wrapper
# ---------------------------------------------------------------------------

class _DryRunEditor:
    def __init__(self, real_editor):
        self._editor = real_editor
        self._count  = 0

    def placeBlock(self, pos, block) -> None:
        self._count += 1
        if self._count <= 20:
            logger.info("  [DRY-RUN] placeBlock(%s, %s)", pos, block)
        elif self._count == 21:
            logger.info("  [DRY-RUN] ... (further placements suppressed)")

    def getBlock(self, pos):
        return self._editor.getBlock(pos)

    def runCommand(self, cmd):
        return self._editor.runCommand(cmd)

    def __getattr__(self, name):
        return getattr(self._editor, name)

    def report(self) -> None:
        logger.info("[DRY-RUN] Total blocks that would be placed: %d", self._count)


# ---------------------------------------------------------------------------
# Heightmap summary
# ---------------------------------------------------------------------------

def _log_heightmap(label: str, analysis) -> None:
    hg = analysis.heightmap_ground
    logger.info(
        "Heightmap %s -- min: %d  max: %d  mean: %.1f  std: %.1f",
        label, int(hg.min()), int(hg.max()), float(hg.mean()), float(hg.std()),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()

    from gdpc.editor import Editor
    from data.configurations import SettlementConfig
    from world_interface.terraforming import terraform_area, terraform_perimeter
    from world_interface.terrain_clearer import clear_lava_pools, remove_sparse_top

    logger.info("Connecting to Minecraft server...")
    editor = Editor(buffering=True)
    try:
        editor.checkConnection()
    except Exception as e:
        logger.error("Could not connect: %s", e)
        sys.exit(1)
    logger.info("Connected.")

    px, py, pz = _get_player_pos(editor)
    logger.info("Player position: (%d, %d, %d)", px, py, pz)

    r      = args.radius
    x_from = px - r
    x_to   = px + r
    z_from = pz - r
    z_to   = pz + r

    logger.info(
        "Test area: radius=%d  x=[%d, %d]  z=[%d, %d]",
        r, x_from, x_to, z_from, z_to,
    )

    analysis      = _build_analysis(editor, x_from, z_from, x_to, z_to)
    active_editor = _DryRunEditor(editor) if args.dry_run else editor
    s_cfg         = SettlementConfig()

    def _run_terraform():
        logger.info(
            "--- terraform_area (passes=%d, smooth_radius=%d) ---",
            args.passes, args.smooth_radius,
        )
        terraform_area(active_editor, analysis,
                       passes=args.passes, smooth_radius=args.smooth_radius)
        _log_heightmap("after terraform_area", analysis)

    def _run_lava():
        logger.info("--- clear_lava_pools ---")
        clear_lava_pools(active_editor, analysis)
        _log_heightmap("after clear_lava_pools", analysis)

    def _run_sparse():
        logger.info("--- remove_sparse_top ---")
        remove_sparse_top(active_editor, analysis)
        _log_heightmap("after remove_sparse_top", analysis)

    def _run_perimeter():
        logger.info("--- terraform_perimeter ---")
        terraform_perimeter(active_editor, analysis, s_cfg)
        _log_heightmap("after terraform_perimeter", analysis)

    op = args.op
    if   op == "terraform":  _run_terraform()
    elif op == "lava":       _run_lava()
    elif op == "sparse":     _run_sparse()
    elif op == "perimeter":  _run_perimeter()
    elif op == "all":
        _run_sparse()
        _run_terraform()
        _run_lava()

    if args.dry_run:
        active_editor.report()
    else:
        logger.info("Flushing blocks to Minecraft...")
        editor.flushBuffer()
        logger.info("Done. Teleport to centre: /tp %d ~ %d", px, pz)


if __name__ == "__main__":
    main()