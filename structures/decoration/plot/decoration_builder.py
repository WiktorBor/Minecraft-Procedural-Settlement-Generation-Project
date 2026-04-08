from __future__ import annotations

import logging
import random

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from data.settlement_entities import Plot
from structures.base.geometry import fill_cuboid, fill_cuboid_wireframe, fill_line
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)


class DecorationBuilder:
    """
    Builds small purely aesthetic decorations — wells or fountains.
    Chosen randomly per plot.
    """

    def __init__(self, palette: PaletteSystem) -> None:
        self.palette = palette

    def build(self, plot: Plot) -> BlockBuffer:
        choice = random.choice(["well", "fountain"])
        if choice == "well":
            return self._build_well(plot)
        else:
            return self._build_fountain(plot)

    def _build_well(self, plot: Plot) -> BlockBuffer:
        """A 3×3 stone-brick well with a roof and hanging lantern."""
        buffer = BlockBuffer()
        x     = plot.x + plot.width  // 2 - 1
        z     = plot.z + plot.depth  // 2 - 1
        y     = plot.y
        wall  = self.palette["wall"]
        acc   = self.palette["accent"]
        found = self.palette["foundation"]
        light = palette_get(self.palette, "light", "minecraft:lantern")

        # Foundation — 4 blocks deep under the 3×3 footprint
        fill_cuboid(buffer, x, y - 4, z, x + 2, y - 1, z + 2, Block(found))

        fill_cuboid_wireframe(buffer, x, y, z, x + 2, y, z + 2, Block(wall))
        buffer.place(x + 1, y, z + 1, Block("minecraft:water"))

        fill_cuboid_wireframe(buffer, x, y + 1, z, x + 2, y + 2, z + 2, Block(wall))

        # Roof beams (accent wood)
        for bx, bz in [(x, z), (x+2, z), (x, z+2), (x+2, z+2), (x+1, z), (x+1, z+2)]:
            buffer.place(bx, y + 3, bz, Block(acc))

        buffer.place(x + 1, y + 3, z + 1, Block(light, {"hanging": "true"}))
        logger.debug("Well built at (%d, %d, %d).", x, y, z)
        return buffer

    def _build_fountain(self, plot: Plot) -> BlockBuffer:
        """Delegate to build_fountain_at using the plot centre."""
        return self.build_fountain_at(
            plot.x + plot.width  // 2,
            plot.y,
            plot.z + plot.depth  // 2,
        )

    def build_fountain_at(self, cx: int, cy: int, cz: int) -> BlockBuffer:
        """A 5×5 cobblestone fountain with a central water pillar."""
        buffer = BlockBuffer()
        x = cx - 2
        z = cz - 2
        y = cy

        stone = self.palette["foundation"]
        wall  = self.palette["wall"]
        light = palette_get(self.palette, "light", "minecraft:lantern")

        # Foundation — 4 blocks deep under the 5×5 footprint
        fill_cuboid(buffer, x, y - 4, z, x + 4, y - 1, z + 4, Block(stone))

        fill_cuboid_wireframe(buffer, x, y, z, x + 4, y, z + 4, Block(stone))
        fill_cuboid(buffer, x + 1, y, z + 1, x + 3, y, z + 3, Block("minecraft:water"))

        # Central pillar (3 blocks tall)
        fill_line(buffer, cx, y + 1, cz, cx, y + 3, cz, Block(wall))
        buffer.place(cx, y + 4, cz, Block("minecraft:water"))

        # Corner lanterns
        for lx, lz in [(x, z), (x + 4, z), (x, z + 4), (x + 4, z + 4)]:
            buffer.place(lx, y + 1, lz, Block(light))

        logger.debug("Fountain built at (%d, %d, %d).", cx, cy, cz)
        return buffer
