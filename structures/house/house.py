from __future__ import annotations

import random

from gdpc.editor import Editor

from structures.base.structure import Structure
from structures.base.structure_agent import StructureAgent
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from .house_builder import HouseBuilder


class HouseAgent(StructureAgent):
    """
    Decides whether a plot is suitable for a house and returns
    build parameters including a random rotation.
    """

    def decide(self, plot: Plot) -> dict:
        patch = self.extract_patch(plot)
        if not self.is_flat(patch, tolerance=1):
            return {"build": False}
        return {
            "build":    True,
            "rotation": random.choice([0, 90, 180, 270]),
        }


class House(Structure):
    """
    A residential medieval house with gabled roof, windows, door and chimney.
    Placed on 'residential' district plots.
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
        if decisions.get("build"):
            # Pass rotation through to the builder — was previously ignored.
            self.builder.build(plot, rotation=decisions.get("rotation", 0))