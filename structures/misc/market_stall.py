"""
structures/misc/market_stall.py
---------------------------------
Self-adjusting market stall with coloured wool canopy.
"""
from __future__ import annotations

import random

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from data.settlement_entities import Plot
from structures.base.geometry import fill_cuboid
from world_interface.block_buffer import BlockBuffer


class MarketStall:
    """
    Small vendor stall: two spruce fence posts + wool canopy.

    Fits any plot; canopy radius scales with the plot size.
    """

    CANOPY_COLORS = ["red", "white", "yellow", "blue", "orange", "lime"]

    def build(
        self,
        plot: Plot,
        palette: PaletteSystem,
        rotation: int = 0,
    ) -> BlockBuffer:
        # Centre on the plot; extend half the plot size in each direction
        cx = plot.x + plot.width  // 2
        cz = plot.z + plot.depth  // 2
        x, y, z = cx, plot.y - 1, cz
        w, d    = plot.width, plot.depth

        buffer = BlockBuffer()

        color = random.choice(self.CANOPY_COLORS)
        wool  = f"minecraft:{color}_wool"
        fence = "minecraft:spruce_fence"
        found = palette_get(palette, "foundation", "minecraft:cobblestone")

        px = max(1, w // 2)
        pz = max(1, d // 2)

        # Foundation — solid block fill 4 blocks below the stall footprint
        fill_cuboid(buffer, x - px, y - 4, z - pz, x + px, y - 1, z + pz, Block(found))

        # Fence posts (front two corners only — back is against a wall typically)
        for iy in range(y + 1, y + 4):
            buffer.place(x - px, iy, z - pz, Block(fence))
            buffer.place(x + px, iy, z - pz, Block(fence))

        # Wool canopy
        for ix in range(x - px, x + px + 1):
            for iz in range(z - pz, z + pz + 1):
                buffer.place(ix, y + 4, iz, Block(wool))

        return buffer