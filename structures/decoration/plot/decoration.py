from __future__ import annotations

from palette.palette_system import PaletteSystem
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
        plot: Plot,
        palette: PaletteSystem,
    ) -> BlockBuffer:
        return DecorationBuilder(palette).build(plot)
