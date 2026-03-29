from __future__ import annotations

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, get_biome_palette
from data.settlement_entities import Plot
from structures.base.structure import Structure
from structures.base.structure_agent import StructureAgent
from structures.tower.tower_builder import TowerBuilder


class TowerAgent(StructureAgent):
    """Decides whether a plot is suitable for a tower."""

    def decide(self, plot: Plot) -> dict:
        patch = self.extract_patch(plot)
        if not self.is_flat(patch, tolerance=3):
            return {"build": False}
        return {"build": True}


class Tower(Structure):
    """
    A medieval stone tower with crenellated parapet.
    Placed on residential or guard plots.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette | None = None,
        height: int = 10,
        width: int = 7,
    ) -> None:
        super().__init__(editor, analysis)
        _palette     = palette or get_biome_palette("medieval")
        self.agent   = TowerAgent(analysis)
        self.builder = TowerBuilder(editor, _palette, height=height, width=width)

    def build(self, plot: Plot) -> None:
        decisions = self.agent.decide(plot)
        if decisions.get("build"):
            self.builder.build(plot)