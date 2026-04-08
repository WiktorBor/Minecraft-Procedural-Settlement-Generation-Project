from __future__ import annotations

from palette.palette_system import PaletteSystem
from data.settlement_entities import Plot
from structures.farm.farm_builder import FarmBuilder
from world_interface.block_buffer import BlockBuffer


class Farm:
    """
    A medieval farm — flat basin with timber frame, water channel, and crops.
    Placed on 'farming' district plots.
    """

    def build(self, plot: Plot, palette: PaletteSystem) -> BlockBuffer:
        return FarmBuilder(palette).build(plot)
