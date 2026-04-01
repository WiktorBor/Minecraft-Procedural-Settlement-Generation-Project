"""Standalone medieval spire tower placed on a plot."""
from __future__ import annotations

from gdpc.editor import Editor

from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from structures.tower.tower_builder import TowerBuilder


class Tower:

    def build(
        self,
        editor: Editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
    ) -> None:
        tw = 5
        cx = plot.x + (plot.width  - tw) // 2
        cz = plot.z + (plot.depth  - tw) // 2

        TowerBuilder(
            editor, palette,
            height=10, width=tw,
            with_door=True, with_windows=True,
            rotation=rotation,
        ).build_at(cx, plot.y, cz)
