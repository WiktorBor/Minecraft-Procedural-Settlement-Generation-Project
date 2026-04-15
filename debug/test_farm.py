"""test_farm.py — standalone farm placement tester."""
from __future__ import annotations

import logging
import sys
import requests
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gdpc import Editor, Block
from palette.palette_system import get_biome_palette
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.orchestrators.farm import build_farm
from world_interface.block_buffer import BlockBuffer
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test_farm")

# =============================================================================
# ✏️  TWEAK ZONE
# =============================================================================
PALETTE_NAME: str = "medieval"
PLOT_WIDTH: int   = 12   # Original builder suggests min 5
PLOT_DEPTH: int   = 10
CLEAR_FIRST: bool = True
# =============================================================================

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """Retrieves player position via HTTP or GDPC fallback."""
    try:
        resp = requests.get("http://localhost:9000/players?includeData=true", timeout=3)
        if resp.ok:
            players = resp.json()
            if players:
                match = re.search(r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]", players[0].get("data", ""))
                if match:
                    return (int(float(match.group(1))), int(float(match.group(2))), int(float(match.group(3))))
    except Exception:
        pass
    
    # Fallback to center of build area if player data is unavailable
    build_area = editor.getBuildArea()
    return (build_area.offset.x + build_area.size.x // 2, 70, build_area.offset.z + build_area.size.z // 2)

def clear_area(editor: Editor, x, y, z, w, d):
    """Clears the volume before building to avoid clipping."""
    positions = [(x + dx, y + dy, z + dz) for dx in range(w + 2) for dz in range(d + 2) for dy in range(-2, 10)]
    editor.placeBlock(positions, Block("minecraft:air"))

def main():
    editor = Editor(buffering=True)
    px, py, pz = _get_player_pos(editor)
    palette = get_biome_palette(PALETTE_NAME)

    # 1. Define the Farm Plot (placed 5 blocks in front of player)
    plot = Plot(x=px + 5, y=py, z=pz, width=PLOT_WIDTH, depth=PLOT_DEPTH, type="farming")
    
    # 2. Setup Shared Build Context
    buffer = BlockBuffer()
    ctx = BuildContext(buffer, palette)

    logger.info("Building farm at %d, %d, %d...", plot.x, plot.y, plot.z)
    
    # 3. Call Orchestrator
    # This applies plot shrinkage and calls rule_farm internally
    build_farm(ctx, plot)

    # 4. Final Placement
    if CLEAR_FIRST:
        clear_area(editor, plot.x, plot.y, plot.z, PLOT_WIDTH, PLOT_DEPTH)
    
    StructurePlacer(editor).place(buffer)
    logger.info("Farm construction complete!")

if __name__ == "__main__":
    main()