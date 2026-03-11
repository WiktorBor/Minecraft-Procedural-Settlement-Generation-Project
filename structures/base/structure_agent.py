from abc import ABC, abstractmethod
from data.build_area import BuildArea
import numpy as np


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

    def extract_patch(self, area: BuildArea, padding=2):
        """
        Extract a terrain heightmap patch around the build site.

        The world heightmap is stored in local build-area coordinates, while
        BuildArea stores absolute world coordinates. Convert from world-space
        to local indices before slicing.
        """

        heightmap = self.world.heightmap_ground
        global_area: BuildArea = self.world.build_area

        # Convert world coordinates to indices relative to the global build area
        ax0 = area.x_from - global_area.x_from
        az0 = area.z_from - global_area.z_from
        ax1 = area.x_to - global_area.x_from
        az1 = area.z_to - global_area.z_from

        x0 = max(0, ax0 - padding)
        z0 = max(0, az0 - padding)
        x1 = min(heightmap.shape[0], ax1 + padding + 1)
        z1 = min(heightmap.shape[1], az1 + padding + 1)

        patch = heightmap[x0:x1, z0:z1]
        return patch

    def compute_slope(self, patch):
        """
        Simple terrain slope measurement.
        """
        if patch.size == 0:
            return 0.0
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
    def decide(self, area: BuildArea):
        """
        Analyse terrain and return building decisions.
        """
        pass