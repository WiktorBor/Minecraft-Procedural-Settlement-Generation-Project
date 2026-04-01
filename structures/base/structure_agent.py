from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import numpy as np

from data.analysis_results import WorldAnalysisResult
from data.build_area import BuildArea
from data.settlement_entities import Plot

logger = logging.getLogger(__name__)


class StructureAgent(ABC):
    """
    Abstract base for terrain-aware structure agents.

    Subclasses implement `decide()` to analyse a plot and return a dict
    of building parameters that the corresponding builder will consume.
    """

    def __init__(self, analysis: WorldAnalysisResult) -> None:
        self.analysis = analysis

    def extract_patch(self, plot: Plot, padding: int = 2) -> np.ndarray | None:
        """
        Extract a heightmap patch around the plot, optionally with padding.

        Args:
            plot: The plot to extract terrain for.
            padding: Extra cells to include around the plot boundary.

        Returns:
            2-D float32 numpy array, or None if the plot is outside the
            build area or produces degenerate bounds.
        """
        heightmap: np.ndarray = self.analysis.heightmap_ground
        area: BuildArea       = self.analysis.best_area

        try:
            local_x, local_z = area.world_to_index(plot.x, plot.z)
        except ValueError:
            logger.error("Plot origin (%d, %d) is outside the build area.", plot.x, plot.z)
            return None

        x0 = max(0, local_x - padding)
        z0 = max(0, local_z - padding)
        x1 = min(heightmap.shape[0], local_x + plot.width  + padding)
        z1 = min(heightmap.shape[1], local_z + plot.depth + padding)

        if x0 >= x1 or z0 >= z1:
            logger.error(
                "Invalid patch bounds for plot %s: x=[%d,%d) z=[%d,%d)",
                plot, x0, x1, z0, z1,
            )
            return None

        return heightmap[x0:x1, z0:z1]

    def compute_slope(self, patch: np.ndarray | None) -> float:
        """
        Return the height range of the patch as a simple slope proxy.

        Returns inf for None or empty patches so callers treat them as
        unbuildable without special-casing.
        """
        if patch is None or patch.size == 0:
            return float("inf")
        return float(patch.max() - patch.min())

    def is_flat(self, patch: np.ndarray | None, tolerance: int = 1) -> bool:
        """Return True if the patch height range is within tolerance."""
        return self.compute_slope(patch) <= tolerance

    @abstractmethod
    def decide(self, plot: Plot) -> dict:
        """
        Analyse terrain under a plot and return building decisions.

        Must return a dict containing at least {'build': bool}.
        """