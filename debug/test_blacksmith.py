"""
test_blacksmith.py
------------------
Updated standalone tester for the refactored Blacksmith Orchestrator.
Uses BuildContext and operates independently of the world heightmap.
"""
from __future__ import annotations

import logging
import sys
import random
import requests
import re
from pathlib import Path

# Ensure project root is in the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gdpc import Editor, Block

from palette.palette_system import get_biome_palette
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.orchestrators.blacksmith import build_blacksmith
from world_interface.block_buffer import BlockBuffer
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_blacksmith")

# =============================================================================
# TWEAK ZONE
# =============================================================================
SEED: int | None = 42
OFFSET: tuple[int, int, int] = (5, 0, 5) 

PLOT_WIDTH: int = 15   # Recommended >= 13, minimum 9
PLOT_DEPTH: int = 12   # Recommended >= 10, minimum 8

PALETTE_NAME: str = "medieval"
CLEAR_FIRST: bool = True
# =============================================================================

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """Retrieves player position via HTTP or Editor methods."""
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

    build_area = editor.getBuildArea()
    cx = build_area.offset.x + build_area.size.x // 2
    cz = build_area.offset.z + build_area.size.z // 2
    return cx, 64, cz

def clear_box(editor: Editor, x: int, y: int, z: int, w: int, d: int, h: int = 25) -> None:
    """Wipes the build area."""
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

    logger.info("Plot origin (Independent): (%d, %d, %d)", hx, hy, hz)

    # 2. Preparation
    plot = Plot(x=hx, y=hy, z=hz, width=PLOT_WIDTH, depth=PLOT_DEPTH, type="industrial")
    palette = get_biome_palette(PALETTE_NAME)

    if CLEAR_FIRST:
        clear_box(editor, hx - 2, hy, hz - 2, PLOT_WIDTH, PLOT_DEPTH)
        editor.flushBuffer()

    # 3. Build using Context and Orchestrator
    buffer = BlockBuffer()
    ctx = BuildContext(
        buffer=buffer, 
        palette=palette,
    )

    logger.info(
        "Building blacksmith %dx%d with medieval palette...",
        PLOT_WIDTH, PLOT_DEPTH
    )

    # Call the new functional orchestrator
    build_blacksmith(ctx, plot)

    if not buffer:
        logger.error("Build failed: Buffer is empty. Check plot constraints.")
        sys.exit(1)

    # 4. Placement
    logger.info("Placing %d blocks via StructurePlacer...", len(buffer))
    StructurePlacer(editor).place(buffer)
    logger.info("Done — /tp %d %d %d", hx, hy + 5, hz)

if __name__ == "__main__":
    main()