from __future__ import annotations
import logging
import sys
import requests
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gdpc import Editor
from palette.palette_system import get_biome_palette
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.orchestrators.dock import build_dock
from world_interface.block_buffer import BlockBuffer
from world_interface.structure_placer import StructurePlacer

logger = logging.getLogger("test_dock")

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """Your specific multi-fallback player position method."""
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

def main():
    logging.basicConfig(level=logging.INFO)
    editor = Editor(buffering=True)
    
    # 1. Fetch player pos using your method
    px, py, pz = _get_player_pos(editor)
    
    # 2. Setup Plot at that location
    plot = Plot(x=px, y=py, z=pz, width=12, depth=10, type="fishing")
    palette = get_biome_palette("medieval")
    
    # 3. Setup Context
    buffer = BlockBuffer()
    ctx = BuildContext(buffer, palette)

    logger.info(f"Placing Dock at Player Position: ({px}, {py}, {pz})")
    
    # 4. Build and Place
    build_dock(ctx, plot)
    if buffer:
        StructurePlacer(editor).place(buffer)
        logger.info("Dock built successfully.")

if __name__ == "__main__":
    main()