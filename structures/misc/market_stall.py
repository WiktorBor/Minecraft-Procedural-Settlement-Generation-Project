"""
structures/misc/market_stall.py
---------------------------------
Self-adjusting market stall with coloured wool canopy.

Uses direct editor calls (no rotation needed — symmetric structure).
"""
from __future__ import annotations

import random

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot


class MarketStall:
    """
    Small vendor stall: two spruce fence posts + wool canopy.

    Fits any plot; canopy radius scales with the plot size.
    """

    CANOPY_COLORS = ["red", "white", "yellow", "blue", "orange", "lime"]

    def build(
        self,
        editor: Editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
    ) -> None:
        x, y, z = plot.x, plot.y, plot.z
        w, d    = plot.width, plot.depth

        color = random.choice(self.CANOPY_COLORS)
        wool  = f"minecraft:{color}_wool"
        fence = "minecraft:spruce_fence"

        px = max(1, w // 2)
        pz = max(1, d // 2)

        # Fence posts (front two corners only — back is against a wall typically)
        for iy in range(y + 1, y + 4):
            editor.placeBlock((x - px, iy, z - pz), Block(fence))
            editor.placeBlock((x + px, iy, z - pz), Block(fence))

        # Wool canopy
        for ix in range(x - px, x + px + 1):
            for iz in range(z - pz, z + pz + 1):
                editor.placeBlock((ix, y + 4, iz), Block(wool))