from __future__ import annotations

import logging
import random

from gdpc import Block
from gdpc.editor import Editor
import gdpc.geometry as geo

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from structures.base.build_context import place_light

logger = logging.getLogger(__name__)


class DecorationBuilder:
    """
    Builds small purely aesthetic decorations — wells or fountains.
    Chosen randomly per plot.
    """

    def __init__(self, editor: Editor, palette: BiomePalette) -> None:
        self.editor  = editor
        self.palette = palette

    def build(self, plot: Plot) -> None:
        choice = random.choice(["well", "fountain"])
        if choice == "well":
            self._build_well(plot)
        else:
            self._build_fountain(plot)

    def _build_well(self, plot: Plot) -> None:
        """A 3×3 stone-brick well with a roof and hanging lantern."""
        x     = plot.x + plot.width  // 2 - 1
        z     = plot.z + plot.depth  // 2 - 1
        y     = plot.y
        wall  = self.palette["wall"]
        acc   = self.palette["accent"]
        found = self.palette["foundation"]
        light = palette_get(self.palette, "light", "minecraft:lantern")

        # Foundation — 4 blocks deep under the 3×3 footprint
        geo.placeCuboid(
            self.editor,
            (x, y - 4, z), (x + 2, y - 1, z + 2),
            Block(found),
        )

        geo.placeCuboidWireframe(
            self.editor, (x, y, z), (x + 2, y, z + 2), Block(wall)
        )
        self.editor.placeBlock((x + 1, y, z + 1), Block("minecraft:water"))

        geo.placeCuboidWireframe(
            self.editor, (x, y + 1, z), (x + 2, y + 2, z + 2), Block(wall)
        )

        # Roof beams (accent wood)
        beam_positions = [
            (x,     y + 3, z    ),
            (x + 2, y + 3, z    ),
            (x,     y + 3, z + 2),
            (x + 2, y + 3, z + 2),
            (x + 1, y + 3, z    ),
            (x + 1, y + 3, z + 2),
        ]
        self.editor.placeBlock(beam_positions, Block(acc))

        place_light(self.editor, (x + 1, y + 3, z + 1), light, hanging=True)
        logger.debug("Well built at (%d, %d, %d).", x, y, z)

    def _build_fountain(self, plot: Plot) -> None:
        """Delegate to build_fountain_at using the plot centre."""
        self.build_fountain_at(
            plot.x + plot.width  // 2,
            plot.y,
            plot.z + plot.depth  // 2,
        )

    def build_fountain_at(self, cx: int, cy: int, cz: int) -> None:
        """A 5×5 cobblestone fountain with a central water pillar."""
        x = cx - 2
        z = cz - 2
        y = cy

        stone = self.palette["foundation"]
        wall  = self.palette["wall"]
        light = palette_get(self.palette, "light", "minecraft:lantern")

        # Foundation — 4 blocks deep under the 5×5 footprint
        geo.placeCuboid(
            self.editor,
            (x, y - 4, z), (x + 4, y - 1, z + 4),
            Block(stone),
        )

        geo.placeCuboidWireframe(
            self.editor, (x, y, z), (x + 4, y, z + 4), Block(stone)
        )
        geo.placeCuboid(
            self.editor, (x + 1, y, z + 1), (x + 3, y, z + 3),
            Block("minecraft:water"),
        )

        # Central pillar (3 blocks tall)
        geo.placeLine(
            self.editor, (cx, y + 1, cz), (cx, y + 3, cz), Block(wall)
        )
        self.editor.placeBlock((cx, y + 4, cz), Block("minecraft:water"))

        # Corner lanterns
        for lx, lz in [(x, z), (x + 4, z), (x, z + 4), (x + 4, z + 4)]:
            self.editor.placeBlock((lx, y + 1, lz), Block(light))

        logger.debug("Fountain built at (%d, %d, %d).", cx, cy, cz)