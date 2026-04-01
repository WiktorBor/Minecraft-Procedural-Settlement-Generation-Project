from __future__ import annotations

from gdpc.editor import Editor

from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from structures.decoration.plot.decoration_builder import DecorationBuilder


class Decoration:
    """
    A purely aesthetic medieval decoration — well or fountain.
    Placed on decoration district plots.
    """

    def build(
        self,
        editor: Editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
    ) -> None:
        DecorationBuilder(editor, palette).build(plot)
