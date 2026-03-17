from __future__ import annotations

from gdpc.editor import Editor

from structures.base.structure import Structure
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from .house_agent import HouseAgent
from .house_builder import HouseBuilder


class House(Structure):
    """
    Composes HouseAgent (site analysis) and HouseBuilder (block placement)
    to produce a complete residential building on a given plot.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        terrain_config: TerrainConfig,
        palette: BiomePalette | None = None,
    ) -> None:
        super().__init__(editor, analysis)
        self.agent   = HouseAgent(analysis)
        self.builder = HouseBuilder(editor, analysis, terrain_config, palette)

    def build(self, plot: Plot) -> None:
        decisions = self.agent.decide(plot)
        self.builder.build_house(plot, decisions)