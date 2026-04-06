"""
debug/test_farm_buffer.py
--------------------------
Tests the full FarmBuilder → BlockBuffer → StructurePlacer pipeline.

Two modes:
  - Offline: verifies the buffer contents without Minecraft
  - In-game: places the farm at the centre of your build area

Run offline:
    python -m debug.test_farm_buffer

Run in-game (requires Minecraft + GDMC HTTP mod + build area set):
    python -m debug.test_farm_buffer --ingame
"""
from __future__ import annotations

import logging
import sys

from data.biome_palettes import get_biome_palette
from data.settlement_entities import Plot
from structures.farm.farm_builder import FarmBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def test_offline() -> None:
    """Verify buffer contents without connecting to Minecraft."""
    palette = get_biome_palette()
    plot    = Plot(x=100, z=200, y=64, width=9, depth=7, type="farming")
    buffer  = FarmBuilder(palette).build(plot)
    blocks  = dict(buffer.items())

    print(f"Total blocks in buffer: {len(blocks)}")
    assert len(blocks) > 0, "Buffer is empty!"

    block_ids = {b.id for b in blocks.values()}
    print(f"Block types placed: {sorted(block_ids)}")

    assert "minecraft:farmland" in block_ids, "No farmland placed!"
    print("  ✓ farmland present")

    assert "minecraft:water" in block_ids, "No water channel placed!"
    print("  ✓ water channel present")

    frame_blocks = {
        "minecraft:oak_log", "minecraft:spruce_log", "minecraft:birch_log",
        "minecraft:dark_oak_log", "minecraft:acacia_log", "minecraft:jungle_log",
    }
    assert block_ids & frame_blocks, "No frame (log) blocks placed!"
    print("  ✓ frame blocks present")

    for (x, y, z), block in blocks.items():
        assert plot.x <= x <= plot.x + plot.width, f"Block x={x} out of plot range"
        assert plot.z <= z <= plot.z + plot.depth,  f"Block z={z} out of plot range"
        assert plot.y - 7 <= y <= plot.y + 2,       f"Block y={y} out of expected height range"
    print("  ✓ all blocks within plot bounds")

    print("\nOffline checks: ALL PASSED")


def test_ingame() -> int:
    """Build the farm and place it in Minecraft via StructurePlacer."""
    from gdpc import Editor
    from utils.http_client import GDMCClient
    from world_interface.structure_placer import StructurePlacer
    from world_interface.terrain_loader import TerrainLoader

    client = GDMCClient()
    if not client.check_connection():
        logger.error("Cannot connect to GDMC HTTP Interface. Is Minecraft running?")
        return 1

    terrain_loader = TerrainLoader(client)

    try:
        build_area = terrain_loader.get_build_area()
    except RuntimeError as e:
        logger.error("%s", e)
        return 1

    cx   = (build_area.x_from + build_area.x_to) // 2
    cz   = (build_area.z_from + build_area.z_to) // 2
    hmap = terrain_loader.get_heightmap(cx, cz, 1, 1, "MOTION_BLOCKING_NO_LEAVES")
    cy   = int(hmap[0, 0])

    plot    = Plot(x=cx, z=cz, y=cy, width=9, depth=7, type="farming")
    palette = get_biome_palette()

    logger.info("Building farm at (%d, %d, %d) size %dx%d", cx, cy, cz, plot.width, plot.depth)
    buffer = FarmBuilder(palette).build(plot)
    logger.info("Buffer contains %d blocks.", len(buffer))

    editor = Editor(buffering=True)
    StructurePlacer(editor).place(buffer)
    logger.info("Farm placed successfully.")

    return 0


def main() -> int:
    if "--ingame" in sys.argv:
        return test_ingame()
    else:
        test_offline()
        return 0


if __name__ == "__main__":
    sys.exit(main())
