"""
Manual terraforming test runner.

Run from project root:
    python tests/test_terraforming.py --help

Examples:
    # Dry-run smooth mode (no plots, downward shaving)
    python tests/test_terraforming.py --x 120 --z -40 --width 64 --depth 64

    # Dry-run platform mode around player (additive, plot-based)
    python tests/test_terraforming.py --around-player --width 48 --depth 48 --auto-plots

    # Apply platform-mode changes
    python tests/test_terraforming.py --x 120 --z -40 --width 64 --depth 64 --auto-plots --apply

    # Apply smooth-mode changes (no plots)
    python tests/test_terraforming.py --x 120 --z -40 --width 64 --depth 64 --apply

    # Use explicit plot footprints for platform mode
    python tests/test_terraforming.py --x 120 --z -40 --width 64 --depth 64 \
      --plot 125,-35,10,10 --plot 150,-20,12,10 --apply
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import requests
from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.build_area import BuildArea
from data.settlement_entities import Plot
from utils.http_client import GDMCClient
from world_interface.terraforming import terraform_area
from world_interface.terrain_loader import TerrainLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_terraforming")


class CountingEditor:
    """Drop-in editor for dry-runs; counts block placement calls only."""

    def __init__(self) -> None:
        self.place_calls = 0

    def placeBlock(self, *_args, **_kwargs) -> None:  # noqa: N802
        self.place_calls += 1


def _get_player_xz() -> tuple[int, int]:
    """Get current player X/Z via GDMC HTTP endpoint."""
    resp = requests.get("http://localhost:9000/players?includeData=true", timeout=3)
    resp.raise_for_status()
    players = resp.json()
    if not players:
        raise RuntimeError("No online players found.")

    data_str = players[0].get("data", "")
    match = re.search(r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]", data_str)
    if not match:
        raise RuntimeError("Could not parse player position from /players response.")
    px = int(float(match.group(1)))
    pz = int(float(match.group(3)))
    return px, pz


def _make_analysis(area: BuildArea, ground: np.ndarray) -> WorldAnalysisResult:
    """Build a minimal WorldAnalysisResult accepted by terraform_area()."""
    w, d = ground.shape
    zeros_f = np.zeros((w, d), dtype=np.float32)
    zeros_b = np.zeros((w, d), dtype=bool)
    biomes = np.full((w, d), "minecraft:plains", dtype=object)
    ocean_floor = np.maximum(ground - 1, 0).astype(np.int32)

    return WorldAnalysisResult(
        best_area=area,
        heightmap_ground=ground.astype(np.int32),
        heightmap_surface=ground.astype(np.int32),
        heightmap_ocean_floor=ocean_floor,
        roughness_map=zeros_f.copy(),
        slope_map=zeros_f.copy(),
        water_mask=zeros_b,
        biomes=biomes,
        scores=zeros_f.copy(),
        plant_thickness=zeros_f.copy(),
        water_distances=zeros_f.copy(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run terraforming on a chosen area.")
    parser.add_argument("--x", type=int, help="Area start X (world coordinate).")
    parser.add_argument("--z", type=int, help="Area start Z (world coordinate).")
    parser.add_argument("--width", type=int, default=64, help="Area width in blocks.")
    parser.add_argument("--depth", type=int, default=64, help="Area depth in blocks.")
    parser.add_argument(
        "--around-player",
        action="store_true",
        help="Center area around player using --x-offset and --z-offset.",
    )
    parser.add_argument(
        "--x-offset", type=int, default=0,
        help="Offset from player X when using --around-player.",
    )
    parser.add_argument(
        "--z-offset", type=int, default=0,
        help="Offset from player Z when using --around-player.",
    )
    # Smooth-mode parameters (used when no --plot / --auto-plots given)
    parser.add_argument("--passes", type=int, default=3, help="Smooth-mode passes.")
    parser.add_argument(
        "--smooth-radius", type=int, default=3,
        help="Neighbourhood radius for smooth mode.",
    )
    parser.add_argument(
        "--max-change-per-pass", type=float, default=1.0,
        help="Max downward change per cell per pass (smooth mode).",
    )
    # Platform-mode parameters
    parser.add_argument(
        "--outer-blend", type=int, default=0,
        help="Blend width outside best_area (platform mode).",
    )
    parser.add_argument(
        "--block-type", type=str, default="minecraft:grass_block",
        help="Fill block type (platform mode).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply world edits. Omit to run dry-run analysis only.",
    )
    parser.add_argument(
        "--plot", action="append", default=[],
        help="Plot footprint as x,z,width,depth (repeatable). Activates platform mode.",
    )
    parser.add_argument(
        "--auto-plots",
        action="store_true",
        help="Create 4 sample plots inside the selected area (activates platform mode).",
    )
    return parser.parse_args()


def _parse_plots(raw: list[str]) -> list[Plot]:
    plots: list[Plot] = []
    for item in raw:
        parts = [p.strip() for p in item.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Invalid --plot '{item}'. Use x,z,width,depth.")
        x, z, w, d = map(int, parts)
        plots.append(Plot(x=x, z=z, width=w, depth=d))
    return plots


def _make_auto_plots(area: BuildArea) -> list[Plot]:
    w = max(6, area.width // 6)
    d = max(6, area.depth // 6)
    return [
        Plot(x=area.x_from + 6, z=area.z_from + 6, width=w, depth=d),
        Plot(x=area.x_to - w - 5, z=area.z_from + 6, width=w, depth=d),
        Plot(x=area.x_from + 6, z=area.z_to - d - 5, width=w, depth=d),
        Plot(x=area.x_to - w - 5, z=area.z_to - d - 5, width=w, depth=d),
    ]


def main() -> None:
    args = parse_args()

    if args.around_player:
        px, pz = _get_player_xz()
        x_from = px - args.width // 2 + args.x_offset
        z_from = pz - args.depth // 2 + args.z_offset
    else:
        if args.x is None or args.z is None:
            raise ValueError("Provide --x and --z, or use --around-player.")
        x_from = args.x
        z_from = args.z

    area = BuildArea(
        x_from=x_from,
        z_from=z_from,
        y_from=-64,
        x_to=x_from + args.width - 1,
        y_to=320,
        z_to=z_from + args.depth - 1,
    )

    logger.info("Target area: x=[%d,%d] z=[%d,%d]", area.x_from, area.x_to, area.z_from, area.z_to)

    client = GDMCClient()
    if not client.check_connection():
        raise RuntimeError("Cannot connect to GDMC server at http://localhost:9000.")

    terrain = TerrainLoader(client)
    ground = terrain.get_heightmap(
        area.x_from, area.z_from, area.width, area.depth,
        "MOTION_BLOCKING_NO_PLANTS",
    )
    ground = np.asarray(ground, dtype=np.int32)
    before = ground.copy()

    analysis = _make_analysis(area, ground)

    plots = _parse_plots(args.plot)
    if args.auto_plots and not plots:
        plots = _make_auto_plots(area)

    platform_mode = bool(plots)

    if platform_mode:
        logger.info(
            "Mode: PLATFORM  plots=%d  outer_blend=%d  block=%s  apply=%s",
            len(plots), args.outer_blend, args.block_type, args.apply,
        )
    else:
        logger.info(
            "Mode: SMOOTH  passes=%d  radius=%d  max_change=%.2f  apply=%s",
            args.passes, args.smooth_radius, args.max_change_per_pass, args.apply,
        )

    editor = Editor(buffering=True) if args.apply else CountingEditor()
    terraform_area(
        editor=editor,          # type: ignore[arg-type]
        analysis=analysis,
        plots=plots or None,
        fill_width=args.width,
        fill_depth=args.depth,
        outer_blend_width=args.outer_blend,
        block_type=args.block_type,
        passes=args.passes,
        smooth_radius=args.smooth_radius,
        max_change_per_pass=args.max_change_per_pass,
    )

    after = analysis.heightmap_ground.astype(np.int32)
    changed_cells = int(np.count_nonzero(after != before))

    if platform_mode:
        total_raised = int(np.sum(np.clip(after - before, 0, None)))
        max_rise     = int(np.max(np.clip(after - before, 0, None)))
        logger.info("Changed cells : %d / %d", changed_cells, before.size)
        logger.info("Total blocks raised (height delta sum): %d", total_raised)
        logger.info("Max single-cell rise: %d", max_rise)
    else:
        total_removed = int(np.sum(np.clip(before - after, 0, None)))
        max_drop      = int(np.max(np.clip(before - after, 0, None)))
        logger.info("Changed cells : %d / %d", changed_cells, before.size)
        logger.info("Total blocks removed (height delta sum): %d", total_removed)
        logger.info("Max single-cell drop: %d", max_drop)

    if args.apply:
        editor.flushBuffer()
        logger.info("Terraform changes applied and flushed to world.")
    else:
        logger.info("Dry-run only (no world edits).")


if __name__ == "__main__":
    main()
