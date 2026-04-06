from __future__ import annotations

from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from structures.decoration.plot.decoration_builder import DecorationBuilder
from world_interface.block_buffer import BlockBuffer


class Decoration:
    """
    A purely aesthetic medieval decoration — well or fountain.
    Placed on decoration district plots.
    """

    def build(
        self,
        _editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
    ) -> BlockBuffer:
        return DecorationBuilder(None, palette).build(plot)
