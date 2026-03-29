from __future__ import annotations

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, get_biome_palette
from data.settlement_entities import Plot
from structures.base.structure import Structure
from structures.base.structure_agent import StructureAgent
from structures.farm.farm_builder import FarmBuilder


class FarmAgent(StructureAgent):
    """Decides whether a plot is suitable for a farm."""

    def decide(self, plot: Plot) -> dict:
        patch = self.extract_patch(plot)
        if not self.is_flat(patch, tolerance=2):
            return {"build": False}
        return {"build": True}


class Farm(Structure):
    """
    A medieval farm — flat basin with timber frame, water channel, and crops.
    Placed on 'farming' district plots.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette | None = None,
    ) -> None:
        super().__init__(editor, analysis)
        self.agent   = FarmAgent(analysis)
        self.builder = FarmBuilder(editor, palette or get_biome_palette("medieval"))

    def build(self, plot: Plot) -> None:
        decisions = self.agent.decide(plot)
        if decisions.get("build"):
            self.builder.build(plot)