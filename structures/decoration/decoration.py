from __future__ import annotations

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, get_biome_palette
from data.settlement_entities import Plot
from structures.base.structure import Structure
from structures.base.structure_agent import StructureAgent
from structures.decoration.decoration_builder import DecorationBuilder


class DecorationAgent(StructureAgent):
    """Decides if a plot is suitable for a decoration (well/fountain)."""

    def decide(self, plot: Plot) -> dict:
        patch = self.extract_patch(plot)
        if not self.is_flat(patch, tolerance=1):
            return {"build": False}
        return {"build": True}


class Decoration(Structure):
    """
    A purely aesthetic medieval decoration — well or fountain.
    Placed on decoration district plots.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette | None = None,
    ) -> None:
        super().__init__(editor, analysis)
        self.agent   = DecorationAgent(analysis)
        self.builder = DecorationBuilder(editor, palette or get_biome_palette("medieval"))

    def build(self, plot: Plot) -> None:
        decisions = self.agent.decide(plot)
        if decisions.get("build"):
            self.builder.build(plot)