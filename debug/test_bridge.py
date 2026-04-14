"""
test_bridge_refactored.py
-------------------------
Standalone bridge placement tester.
Builds both an infrastructure bridge and a tavern-style connector.
"""
from __future__ import annotations

import logging
import sys
import requests
import re
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from gdpc import Editor, Block
from palette.palette_system import get_biome_palette
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.orchestrators.primitives.bridge import build_bridge
from world_interface.block_buffer import BlockBuffer
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test_bridge")

# =============================================================================
# ✏️  TWEAK ZONE
# =============================================================================
PALETTE_NAME: str = "medieval"
CLEAR_FIRST: bool = True
# =============================================================================

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """Robust player position retrieval."""
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
    
    # Fallback to build area center
    build_area = editor.getBuildArea()
    return (build_area.offset.x + build_area.size.x // 2, 70, build_area.offset.z + build_area.size.z // 2)

def clear_area(editor: Editor, x, y, z, w, d):
    """Clears a safety volume for testing."""
    positions = [(x + dx, y + dy, z + dz) for dx in range(w) for dz in range(d) for dy in range(0, 10)]
    editor.placeBlock(positions, Block("minecraft:air"))

def main():
    editor = Editor(buffering=True)
    px, py, pz = _get_player_pos(editor)
    palette = get_biome_palette(PALETTE_NAME)

    # --- 1. TEST INFRASTRUCTURE BRIDGE (STONE ARCHES) ---
    # Placed 5 blocks to the East
    stone_plot = Plot(x=px + 5, y=py, z=pz, width=16, depth=5)
    stone_buffer = BlockBuffer()
    stone_ctx = BuildContext(stone_buffer, palette)
    
    logger.info("Building Infrastructure Bridge...")
    build_bridge(stone_ctx, stone_plot, structure_role="infrastructure", span_axis="x")
    
    if CLEAR_FIRST: clear_area(editor, stone_plot.x, stone_plot.y, stone_plot.z, 16, 5)
    StructurePlacer(editor).place(stone_buffer)

    # --- 2. TEST CONNECTOR BRIDGE (TAVERN/BELFRY STYLE) ---
    # Placed 15 blocks to the East
    wood_plot = Plot(x=px + 5, y=py, z=pz + 10, width=12, depth=3)
    wood_buffer = BlockBuffer()
    wood_ctx = BuildContext(wood_buffer, palette)
    
    logger.info("Building Tavern-style Connector Bridge...")
    build_bridge(wood_ctx, wood_plot, structure_role="connector", span_axis="x")
    
    if CLEAR_FIRST: clear_area(editor, wood_plot.x, wood_plot.y, wood_plot.z, 12, 3)
    StructurePlacer(editor).place(wood_buffer)

    logger.info(f"Done! Check in-game at {px+5}, {py}, {pz}")

if __name__ == "__main__":
    main()