import sys
import logging
import requests
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gdpc import Editor
from utils.http_client import GDMCClient
from world_interface.terrain_loader import TerrainLoader
from palette.palette_system import get_biome_palette
from world_interface.structure_placer import StructurePlacer
from structures.base.build_context import BuildContext
from data.build_area import BuildArea
from world_interface.block_buffer import BlockBuffer

# Consolidated Logic Imports
from structures.orchestrators.fortification import build_fortification_settlement

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("test_arched_perimeter")

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """Retrieves player position via HTTP or GDPC fallback."""
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
    
    pos = editor.getPlayerPos()
    return int(pos.x), int(pos.y), int(pos.z)

def main():
    editor = Editor(buffering=True)
    client = GDMCClient()
    loader = TerrainLoader(client)
    
    # 1. Get Player Position
    px, py, pz = _get_player_pos(editor)
    
    # 2. Define Build Area and Fetch Heightmap
    area_obj = BuildArea(px-50, py-25, pz-50, px+50, py+25, pz+50)
    heightmap = loader.get_heightmap(area_obj.x_from, area_obj.z_from, 100, 100, "MOTION_BLOCKING_NO_LEAVES")

    # 3. Setup Context
    buffer = BlockBuffer()
    palette = get_biome_palette("medieval")
    ctx = BuildContext(buffer, palette)
    
    # 4. Set Wall Height using Player's Y as the Base
    # The wall_top_y is the player's Y + desired wall height (e.g., 6)
    target_top_y = py + 6 

    # 5. Build Entire Perimeter
    logger.info(f"Building double-wall perimeter starting at Player Y={py}")
    build_fortification_settlement(
        ctx=ctx,
        palette=palette,
        heightmap=heightmap,
        area=area_obj,
        wall_top_y=target_top_y,
        tower_width=5,
        buildings=[]
    )
    
    # 6. Place results
    StructurePlacer(editor).place(buffer)
    print(f"Fortification complete! Walkway is level with Y={target_top_y}.")

if __name__ == "__main__":
    main()