"""
test_spire_tower.py
-------------------
Updated tester for the compositional Spire Tower orchestrator.
Uses player position and independent plot logic (no heightmap).
"""
from __future__ import annotations

import logging
import sys
import random
import requests
import re
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gdpc import Editor, Block

from palette.palette_system import get_biome_palette
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.orchestrators.spire_tower import build_spire_tower
from world_interface.block_buffer import BlockBuffer
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_spire_tower")

# =============================================================================
# TWEAK ZONE
# =============================================================================
SEED: int | None = 42
OFFSET: tuple[int, int, int] = (5, 0, 5)  # Relative to player (x, y_offset, z)
PLOT_WIDTH: int = 16   # Tower (5) + House (min 5)
PLOT_DEPTH: int = 10   
PALETTE_NAME: str = "medieval"
CLEAR_FIRST: bool = True
ROTATION: int = 0   
# =============================================================================

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """Tries multiple methods to find the player, falling back to build area center."""
    try:
        resp = requests.get("http://localhost:9000/players?includeData=true", timeout=3)
        if resp.ok:
            players = resp.json()
            if players:
                match = re.search(
                    r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]",
                    players[0].get("data", ""),
                )
                if match:
                    return (int(float(match.group(1))),
                            int(float(match.group(2))),
                            int(float(match.group(3))))
    except Exception as e:
        logger.debug("HTTP /players failed: %s", e)

    try:
        pos = editor.getPlayerPos()
        return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayerPos() failed: %s", e)

    try:
        players = editor.getPlayers()
        if players:
            pos = players[0].pos
            return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayers() failed: %s", e)

    build_area = editor.getBuildArea()
    cx = build_area.offset.x + build_area.size.x // 2
    cz = build_area.offset.z + build_area.size.z // 2
    logger.warning("Falling back to build area centre.")
    return cx, 64, cz

def clear_box(editor: Editor, x: int, y: int, z: int, w: int, d: int, h: int = 40) -> None:
    """Wipes the build area to air before placement."""
    positions = [
        (x + dx, y + dy, z + dz)
        for dx in range(w + 4)
        for dz in range(d + 4)
        for dy in range(-2, h)
    ]
    logger.info("Clearing %d blocks...", len(positions))
    editor.placeBlock(positions, Block("minecraft:air"))

def main() -> None:
    if SEED is not None:
        random.seed(SEED)

    logger.info("Connecting to Minecraft...")
    editor = Editor(buffering=True)

    # 1. Coordinate Setup
    px, py, pz = _get_player_pos(editor)
    ox, oy_offset, oz = OFFSET
    hx, hy, hz = px + ox, py + oy_offset, pz + oz

    logger.info("Plot origin (based on player): (%d, %d, %d)", hx, hy, hz)

    # 2. Data Preparation
    plot = Plot(x=hx, y=hy, z=hz, width=PLOT_WIDTH, depth=PLOT_DEPTH, type="residential")
    palette = get_biome_palette(PALETTE_NAME)

    if CLEAR_FIRST:
        clear_box(editor, hx - 2, hy, hz - 2, PLOT_WIDTH, PLOT_DEPTH)
        editor.flushBuffer()

    # 3. Build using Context and Orchestrator
    buffer = BlockBuffer()
    # Building axis-aligned (0); post-rotation logic would happen after build()
    ctx = BuildContext(
        buffer=buffer, 
        palette=palette,
    )

    logger.info("Assembling Spire Tower (Tower + House Wing)...")
    build_spire_tower(ctx, plot)

    if not buffer:
        logger.error("Build failed: Buffer is empty.")
        sys.exit(1)

    # 4. Final Placement
    logger.info("Placing %d blocks via StructurePlacer...", len(buffer))
    StructurePlacer(editor).place(buffer)
    logger.info("Done — /tp %d %d %d", hx, hy + 5, hz)

if __name__ == "__main__":
    main()