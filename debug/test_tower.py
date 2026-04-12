"""
test_tower.py
-------------
Final modular version. 
Tests the build_tower orchestrator relative to the player position.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the project root is in the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gdpc import Editor, Block
from palette.palette_system import get_biome_palette
from data.settlement_entities import Plot
from structures.orchestrators.tower import build_tower  # The new orchestrator
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("test_tower")

# =============================================================================
# SETTINGS
# =============================================================================
PALETTE_NAME: str = "medieval"
ROTATION: int     = 0
CLEAR_FIRST: bool = True
OFFSET: tuple     = (5, 0, 5) # 5 blocks away from player
# =============================================================================

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    import requests, re
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

def main() -> None:
    editor = Editor(buffering=True)
    px, py, pz = _get_player_pos(editor)
    
    # Calculate build origin
    hx, hy, hz = px + OFFSET[0], py + OFFSET[1], pz + OFFSET[2]
    
    # We use a 10x10 plot so the 5x5 tower has room to breathe
    plot = Plot(x=hx, y=hy, z=hz, width=10, depth=10, type="residential")
    palette = get_biome_palette(PALETTE_NAME)

    if CLEAR_FIRST:
        # Clear a slightly larger area for visibility
        editor.placeBlock([(hx + dx, hy + dy, hz + dz) 
                           for dx in range(12) for dz in range(12) for dy in range(25)], 
                          Block("minecraft:air"))
        editor.flushBuffer()

    logger.info(f"Testing Tower Orchestrator at ({hx}, {hy}, {hz})")

    # CALLING THE NEW ORCHESTRATOR
    # We pass the role "tower_house" to test if windows and doors generate
    buf = build_tower(
        palette, 
        hx, hy, hz, 
        w=5, h=10, d=5, 
        structure_role="clock_tower"
    )

    if buf:
        StructurePlacer(editor).place(buf)
        print(f"Tower built! /tp {hx} {hy + 5} {hz}")
    else:
        logger.error("Orchestrator returned empty buffer.")

if __name__ == "__main__":
    main()