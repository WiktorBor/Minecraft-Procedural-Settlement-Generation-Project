from __future__ import annotations

import random
import logging

from gdpc import Block
from gdpc.editor import Editor
import gdpc.geometry as geo

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot

logger = logging.getLogger(__name__)

# Crop pairs placed either side of the central water channel
_CROP_PAIRS: list[tuple[str, str]] = [
    ("minecraft:wheat",   "minecraft:carrots"),
    ("minecraft:wheat",   "minecraft:potatoes"),
    ("minecraft:carrots", "minecraft:_seeds"),
]


class FarmBuilder:
    """
    Builds a small medieval farm plot: a timber-framed basin with farmland,
    a central water channel, and crops.

    Layout (width=7 example):
        ┌─────────────────┐  ← oak log frame (y-1)
        │ crop | water | crop │  ← farmland + water + crops (y, y+1)
        └─────────────────┘
    """

    def __init__(
        self,
        editor: Editor,
        palette: BiomePalette,
    ) -> None:
        self.editor  = editor
        self.palette = palette

    def build(self, plot: Plot) -> None:
        """Build a farm on the given plot."""
        x, z = plot.x, plot.z
        y    = plot.y
        w, d = plot.width, plot.depth

        # Randomise size slightly within the plot footprint
        w = max(5, w - random.choice([0, 2]))
        d = max(5, d - random.choice([0, 2]))

        basin_block = palette_get(self.palette, "accent", "minecraft:oak_log")
        crops_left, crops_right = random.choice(_CROP_PAIRS)
        channel_x = x + w // 2

        # --- base frame (y-1) ---
        geo.placeCuboid(
            self.editor,
            (x, y - 1, z), (x + w - 1, y - 1, z + d - 1),
            Block(basin_block),
        )

        # --- perimeter frame (y) ---
        geo.placeCuboidWireframe(
            self.editor,
            (x, y, z), (x + w - 1, y, z + d - 1),
            Block(basin_block),
        )

        # --- farmland interior ---
        geo.placeCuboid(
            self.editor,
            (x + 1, y, z + 1), (x + w - 2, y, z + d - 2),
            Block("minecraft:farmland"),
        )

        # --- central water channel ---
        geo.placeLine(
            self.editor,
            (channel_x, y, z + 1), (channel_x, y, z + d - 2),
            Block("minecraft:water"),
        )

        # --- crops either side of channel ---
        if channel_x - 1 >= x + 1:
            geo.placeCuboid(
                self.editor,
                (x + 1, y + 1, z + 1), (channel_x - 1, y + 1, z + d - 2),
                Block(crops_left, {"age": "7"}),
            )
        if channel_x + 1 <= x + w - 2:
            geo.placeCuboid(
                self.editor,
                (channel_x + 1, y + 1, z + 1), (x + w - 2, y + 1, z + d - 2),
                Block(crops_right, {"age": "7"}),
            )

        # --- lanterns at corners for medieval feel ---
        light = palette_get(self.palette, "light", "minecraft:lantern")
        for lx, lz in [(x, z), (x + w - 1, z), (x, z + d - 1), (x + w - 1, z + d - 1)]:
            self.editor.placeBlock((lx, y + 1, lz), Block(light))

        logger.debug("Farm built at (%d, %d, %d) size %dx%d.", x, y, z, w, d)