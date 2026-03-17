from __future__ import annotations

import random

from structures.base.structure_agent import StructureAgent
from data.settlement_entities import Plot


class HouseAgent(StructureAgent):
    """
    Agent responsible for deciding where and how to build houses.
    Analyses terrain and returns building parameters.
    """

    def decide(self, plot: Plot) -> dict:
        """
        Analyse the plot and return building decisions.

        Args:
            plot: The plot to evaluate.

        Returns:
            dict with at minimum a 'build' key (bool).
            If build=True, also contains 'rotation'.
        """
        patch = self.extract_patch(plot)
        if not self.is_flat(patch, tolerance=1):
            return {"build": False}

        return {
            "build":    True,
            "rotation": random.choice([0, 90, 180, 270]),
        }