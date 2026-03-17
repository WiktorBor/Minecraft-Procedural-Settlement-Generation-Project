from abc import ABC, abstractmethod
from data.build_area import BuildArea
import numpy as np
from data.settlement_entities import Plot


class StructureAgent(ABC):
    """
    Base class for terrain-aware structure agents.
    Responsible for analysing terrain and deciding structure parameters.
    """

    def __init__(self, world):
        self.world = world

    # ----------------------------
    # Terrain utilities
    # ----------------------------

    def extract_patch(self, plot: Plot, padding=2) -> np.ndarray:
        """
        Extract a terrain heightmap patch around the build site.
        """

        heightmap: np.ndarray = self.world.heightmap_ground
        best_area: BuildArea = self.world.best_area

        local_x, local_z = best_area.world_to_index(plot.x, plot.z)

        x0 = max(0, local_x - padding)
        z0 = max(0, local_z - padding)
        x1 = min(heightmap.shape[0], local_x + plot.width + padding)
        z1 = min(heightmap.shape[1], local_z + plot.depth + padding)

        if x0 >= x1 or z0 >= z1:
            print("❌ Invalid patch bounds!")
            print(f"Plot: {plot}")
            print(f"x0={x0}, x1={x1}, z0={z0}, z1={z1}")
            print(f"Width={plot.width}, Depth={plot.depth}")


        patch = heightmap[x0:x1, z0:z1]
        return patch

    def compute_slope(self, patch):
        """
        Simple terrain slope measurement.
        """
        if patch.size == 0:
            return float('inf')
        return patch.max() - patch.min()

    def is_flat(self, patch, tolerance=1):
        """
        Check if terrain is flat enough for building.
        """
        return self.compute_slope(patch) <= tolerance

    # ----------------------------
    # Decision interface
    # ----------------------------

    @abstractmethod
    def decide(self, plot: Plot):
        """
        Analyse terrain under a plot and return building decisions.
        """
        pass