"""
test_house_refactored.py
------------------------
Refactored house placement tester.
"""
from __future__ import annotations

import logging
import sys
import random
import requests
import re
from pathlib import Path

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from gdpc import Editor, Block

from palette.palette_system import get_biome_palette
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.house.house import build_house_settlement
from world_interface.block_buffer import BlockBuffer
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_house")

# =============================================================================
# ✏️  TWEAK ZONE
# =============================================================================
SEED: int | None = 42
OFFSET: tuple[int, int, int] = (5, 0, 5)
PLOT_WIDTH: int = 10
PLOT_DEPTH: int = 9
PALETTE_NAME: str = "medieval"
CLEAR_FIRST: bool = True
ROTATION: int = 0

# The orchestrator uses these to override the Grammar's default logic
FORCE_PARAMS: dict | None = {
    "wall_h": 7,
    "structure_role": "cottage", # or "cottage" to test the refactored cottage logic
    "bridge_side": "north"     # Direction for door/roof alignment
}

# =============================================================================

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """Robust player position retrieval using your fallback method."""
    try:
        resp = requests.get("http://localhost:9000/players?includeData=true", timeout=3)
        if resp.ok:
            players = resp.json()
            if players:
                match = re.search(r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]", players[0].get("data", ""))
                if match:
                    return (int(float(match.group(1))), int(float(match.group(2))), int(float(match.group(3))))
    except Exception as e:
        logger.debug("HTTP /players failed: %s", e)

    try:
        pos = editor.getPlayerPos()
        return int(pos.x), int(pos.y), int(pos.z)
    except Exception:
        build_area = editor.getBuildArea()
        return build_area.offset.x + build_area.size.x // 2, 64, build_area.offset.z + build_area.size.z // 2

def clear_box(editor: Editor, x: int, y: int, z: int, w: int, d: int, h: int = 20) -> None:
    positions = [(x + dx, y + dy, z + dz) for dx in range(w + 4) for dz in range(d + 4) for dy in range(-2, h)]
    editor.placeBlock(positions, Block("minecraft:air"))

def main() -> None:
    if SEED is not None:
        random.seed(SEED)

    editor = Editor(buffering=True)
    px, py, pz = _get_player_pos(editor)
    
    hx, hy_off, hz = px + OFFSET[0], OFFSET[1], pz + OFFSET[2]
    hy = py + hy_off 

    # 1. Define the Plot
    plot = Plot(x=hx, y=hy, z=hz, width=PLOT_WIDTH, depth=PLOT_DEPTH, type="residential")
    palette = get_biome_palette(PALETTE_NAME)

    # 2. Clear area
    if CLEAR_FIRST:
        clear_box(editor, hx - 2, hy, hz - 2, PLOT_WIDTH, PLOT_DEPTH)
        editor.flushBuffer()

    # 3. Setup the Refactored Build Context
    # In the new system, we create the buffer and context manually for the orchestrator
    buffer = BlockBuffer()
    ctx = BuildContext(buffer, palette)

    logger.info(f"Building Refactored House at ({hx}, {hy}, {hz})...")

    # 4. Call the Orchestrator
    # We pass the bridge_side and structure_role from our Tweak Zone
    build_house_settlement(
        ctx, 
        plot,  
        bridge_side=FORCE_PARAMS.get("bridge_side"),
        structure_role=FORCE_PARAMS.get("structure_role", "house"),
    )

    # 5. Place the result
    StructurePlacer(editor).place(buffer)
    logger.info("Done.")

if __name__ == "__main__":
    main()