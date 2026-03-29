from __future__ import annotations

import random

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from structures.base.structure import Structure
from structures.base.structure_agent import StructureAgent
from structures.house.house_grammar import HouseGrammar


class HouseAgent(StructureAgent):
    """Decides whether a plot is suitable for a house."""

    def decide(self, plot: Plot) -> dict:
        patch = self.extract_patch(plot)
        if not self.is_flat(patch, tolerance=2):
            return {"build": False}
        return {
            "build":    True,
            "rotation": random.choice([0, 90, 180, 270]),
        }


class House(Structure):
    """
    A medieval residential house with grammar-driven exterior and furnished interior.
    Front face orients toward the nearest road cell.
    Single storey for small plots; two storeys for plots >= 10x10.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette | None = None,
    ) -> None:
        super().__init__(editor, analysis)
        self.palette = palette
        self.agent   = HouseAgent(analysis)
        self.grammar = HouseGrammar(editor, palette)

    def build(self, plot: Plot) -> None:
        decisions = self.agent.decide(plot)
        if decisions.get("build"):
            self.grammar.build(plot, rotation=decisions["rotation"])