from __future__ import annotations

import logging
import random

from gdpc import Block

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from structures.base.geometry import fill_cuboid, fill_cuboid_wireframe, fill_line
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)

_CROP_PAIRS: list[tuple[str, str]] = [
    ("minecraft:wheat",   "minecraft:carrots"),
    ("minecraft:wheat",   "minecraft:potatoes"),
    ("minecraft:carrots", "minecraft:beetroots"),
]

_CROP_MAX_AGE: dict[str, int] = {
    "minecraft:beetroots": 3,
}


class FarmBuilder:
    """
    Builds a small medieval farm plot: a timber-framed basin with farmland,
    a central water channel, and crops.

    Returns a BlockBuffer — does not write to Minecraft directly.
    """

    def __init__(self, palette: BiomePalette) -> None:
        self.palette = palette

    def build(self, plot: Plot) -> BlockBuffer:
        """Build a farm on the given plot and return the block buffer."""
        buffer = BlockBuffer()

        x, z = plot.x, plot.z
        y    = plot.y
        w, d = plot.width, plot.depth

        w = max(5, w - random.choice([0, 2]))
        d = max(5, d - random.choice([0, 2]))

        basin_block             = palette_get(self.palette, "accent",     "minecraft:oak_log")
        found_block             = palette_get(self.palette, "foundation", "minecraft:cobblestone")
        crops_left, crops_right = random.choice(_CROP_PAIRS)
        channel_x               = x + w // 2

        # Foundation
        fill_cuboid(
            buffer,
            x, y - 6, z, x + w - 1, y - 2, z + d - 1,
            Block(found_block),
        )

        # Base frame (y-1)
        fill_cuboid(
            buffer,
            x, y - 1, z, x + w - 1, y - 1, z + d - 1,
            Block(basin_block),
        )

        # Perimeter frame (y)
        fill_cuboid_wireframe(
            buffer,
            x, y, z, x + w - 1, y, z + d - 1,
            Block(basin_block),
        )

        # Farmland interior
        fill_cuboid(
            buffer,
            x + 1, y, z + 1, x + w - 2, y, z + d - 2,
            Block("minecraft:farmland"),
        )

        # Central water channel
        fill_line(
            buffer,
            channel_x, y, z + 1, channel_x, y, z + d - 2,
            Block("minecraft:water"),
        )

        # Crops either side of channel
        age_left  = str(_CROP_MAX_AGE.get(crops_left,  7))
        age_right = str(_CROP_MAX_AGE.get(crops_right, 7))
        if channel_x - 1 >= x + 1:
            fill_cuboid(
                buffer,
                x + 1, y + 1, z + 1, channel_x - 1, y + 1, z + d - 2,
                Block(crops_left, {"age": age_left}),
            )
        if channel_x + 1 <= x + w - 2:
            fill_cuboid(
                buffer,
                channel_x + 1, y + 1, z + 1, x + w - 2, y + 1, z + d - 2,
                Block(crops_right, {"age": age_right}),
            )

        # Lanterns at corners
        light = palette_get(self.palette, "light", "minecraft:lantern")
        for lx, lz in [
            (x,         z        ),
            (x + w - 1, z        ),
            (x,         z + d - 1),
            (x + w - 1, z + d - 1),
        ]:
            buffer.place(lx, y + 1, lz, Block(light))

        logger.debug("Farm built at (%d, %d, %d) size %dx%d.", x, y, z, w, d)
        return buffer
