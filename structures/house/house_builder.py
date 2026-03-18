"""
Residential building builder — delegates to HouseGrammar for all block placement.

Keeps the same public interface as before (HouseBuilder.build(plot)) so
nothing in settlement_generator.py needs to change.
"""
from __future__ import annotations

from gdpc.editor import Editor

from world_interface.terrain_clearer import clear_area
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from data.settlement_entities import Plot
from data.biome_palettes import BiomePalette, get_biome_palette
from .house_grammar import HouseGrammar


class HouseBuilder:
    """
    Thin wrapper that clears vegetation then delegates to HouseGrammar.

    HouseGrammar contains all shape-grammar logic: foundation, body,
    half-timbered upper storey, facade with door surround and shutters,
    roof variants (gabled/steep/cross-gabled), chimney, lean-to extension,
    and decorative details (lanterns, barrels, porch posts).
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        terrain_config: TerrainConfig,
        palette: BiomePalette | None = None,
    ) -> None:
        self.editor         = editor
        self.analysis       = analysis
        self.terrain_config = terrain_config
        self.palette        = palette if palette is not None else get_biome_palette()
        self._grammar       = HouseGrammar(editor, self.palette)

    def build(self, plot: Plot, rotation: int = 0) -> None:
        """
        Clear vegetation around the plot then build via HouseGrammar.

        Args:
            plot:     The plot to build on.
            rotation: Rotation in degrees (0, 90, 180, 270).
        """
        clear_area(
            editor=self.editor,
            analysis=self.analysis,
            plot=plot,
            config=self.terrain_config,
        )
        self._grammar.build(plot, rotation=rotation)