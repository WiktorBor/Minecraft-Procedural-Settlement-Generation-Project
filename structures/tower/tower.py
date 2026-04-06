"""Standalone medieval spire tower placed on a plot."""
from __future__ import annotations

from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from structures.tower.tower_builder import TowerBuilder
from world_interface.block_buffer import BlockBuffer


class Tower:

    def build(
        self,
        _editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
    ) -> BlockBuffer:
        tw = 5
        cx = plot.x + (plot.width  - tw) // 2
        cz = plot.z + (plot.depth  - tw) // 2

        return TowerBuilder(
            None, palette,
            height=10, width=tw,
            with_door=True, with_windows=True,
            rotation=rotation,
        ).build_at(cx, plot.y, cz)
