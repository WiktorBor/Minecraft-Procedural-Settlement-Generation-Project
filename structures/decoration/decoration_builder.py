from __future__ import annotations

import random
import logging

from gdpc import Block
from gdpc.editor import Editor
import gdpc.geometry as geo

from data.biome_palettes import BiomePalette, palette_get
from structures.components import place_light
from data.settlement_entities import Plot

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

    # ------------------------------------------------------------------
    # Well
    # ------------------------------------------------------------------
    def _build_well(self, plot: Plot) -> None:
        """A 3×3 stone-brick well with a roof and hanging lantern."""
        x, z = plot.x + plot.width // 2 - 1, plot.z + plot.depth // 2 - 1
        y    = plot.y
        wall = self.palette["wall"]
        acc  = self.palette["accent"]
        light = palette_get(self.palette, "light", "minecraft:lantern")

        # Base ring
        geo.placeCuboidWireframe(
            self.editor, (x, y, z), (x + 2, y, z + 2), Block(wall)
        )
        # Water inside
        self.editor.placeBlock((x + 1, y, z + 1), Block("minecraft:water"))

        # Walls up 2 blocks
        geo.placeCuboidWireframe(
            self.editor, (x, y + 1, z), (x + 2, y + 2, z + 2), Block(wall)
        )

        # Roof beams (accent wood)
        self.editor.placeBlock((x,     y + 3, z    ), Block(acc))
        self.editor.placeBlock((x + 2, y + 3, z    ), Block(acc))
        self.editor.placeBlock((x,     y + 3, z + 2), Block(acc))
        self.editor.placeBlock((x + 2, y + 3, z + 2), Block(acc))
        self.editor.placeBlock((x + 1, y + 3, z    ), Block(acc))
        self.editor.placeBlock((x + 1, y + 3, z + 2), Block(acc))

        # Hanging lantern
        place_light(self.editor, (x + 1, y + 3, z + 1), light, hanging=True)
        logger.debug("Well built at (%d, %d, %d).", x, y, z)

    # ------------------------------------------------------------------
    # Fountain
    # ------------------------------------------------------------------
    def _build_fountain(self, plot: Plot) -> None:
        """A 5×5 cobblestone fountain with a central water pillar."""
        x, z  = plot.x + plot.width // 2 - 2, plot.z + plot.depth // 2 - 2
        y     = plot.y
        stone = self.palette["foundation"]
        wall  = self.palette["wall"]
        light = palette_get(self.palette, "light", "minecraft:lantern")

        # Outer ring basin (1 block tall)
        geo.placeCuboidWireframe(
            self.editor, (x, y, z), (x + 4, y, z + 4), Block(stone)
        )
        # Fill interior with water
        geo.placeCuboid(
            self.editor, (x + 1, y, z + 1), (x + 3, y, z + 3),
            Block("minecraft:water")
        )

        # Central pillar (3 blocks tall)
        cx, cz = x + 2, z + 2
        geo.placeLine(
            self.editor, (cx, y + 1, cz), (cx, y + 3, cz), Block(wall)
        )
        # Water source on top of pillar
        self.editor.placeBlock((cx, y + 4, cz), Block("minecraft:water"))

        # Corner lanterns
        for lx, lz in [(x, z), (x + 4, z), (x, z + 4), (x + 4, z + 4)]:
            self.editor.placeBlock((lx, y + 1, lz), Block(light))

        logger.debug("Fountain built at (%d, %d, %d).", x, y, z)