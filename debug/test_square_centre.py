"""
test_plaza.py
-------------
Standalone independent tester for the Circular Stone Plaza.
Tests both Small Fountain and Grand Spire styles based on plot size.
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
from structures.orchestrators.plaza import build_square_centre
from world_interface.block_buffer import BlockBuffer
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_plaza")

# =============================================================================
# CONFIGURATION
# =============================================================================
SEED: int | None = 42
OFFSET: tuple[int, int, int] = (5, 0, 5) 

# Change these to test different styles:
# Width/Depth < 16 (Radius < 8) -> Small Fountain
# Width/Depth >= 16 (Radius >= 8) -> Grand Spire
PLOT_WIDTH: int = 20   
PLOT_DEPTH: int = 20   

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
    return build_area.offset.x + build_area.size.x // 2, 64, build_area.offset.z + build_area.size.z // 2

def clear_box(editor: Editor, x: int, y: int, z: int, w: int, d: int, h: int = 40) -> None:
    """Clears volume to air."""
    positions = [
        (x + dx, y + dy, z + dz)
        for dx in range(w + 4)
        for dz in range(d + 4)
        for dy in range(-2, h)
    ]
    editor.placeBlock(positions, Block("minecraft:air"))

def main() -> None:
    if SEED is not None:
        random.seed(SEED)

    logger.info("Initializing GDPC Editor...")
    editor = Editor(buffering=True)

    # 1. Coordinate and Plot Setup
    px, py, pz = _get_player_pos(editor)
    ox, oy, oz = OFFSET
    hx, hy, hz = px + ox, py + oy, pz + oz

    logger.info(f"Target Plaza Center: ({hx + PLOT_WIDTH//2}, {hy}, {hz + PLOT_DEPTH//2})")

    plot = Plot(x=hx, y=hy, z=hz, width=PLOT_WIDTH, depth=PLOT_DEPTH, type="urban")
    palette = get_biome_palette(PALETTE_NAME)

    # 2. Preparation
    if CLEAR_FIRST:
        logger.info("Clearing build area...")
        clear_box(editor, hx - 2, hy, hz - 2, PLOT_WIDTH, PLOT_DEPTH)
        editor.flushBuffer()

    # 3. Assemble the Structure
    buffer = BlockBuffer()
    ctx = BuildContext(
        buffer=buffer, 
        palette=palette,
    )

    logger.info(f"Orchestrating Plaza (Radius: {min(PLOT_WIDTH, PLOT_DEPTH)//2})...")
    build_square_centre(ctx, plot)

    if not buffer:
        logger.error("Error: Plaza logic generated 0 blocks.")
        sys.exit(1)

    # 4. Placement
    logger.info(f"Placing {len(buffer)} blocks...")
    StructurePlacer(editor).place(buffer)
    
    logger.info(f"Done — /tp {hx + PLOT_WIDTH//2} {hy + 5} {hz + PLOT_DEPTH//2}")

if __name__ == "__main__":
    main()