from data.build_area import BuildArea
from world_interface.terrain_loader import TerrainLoader
import numpy as np
from typing import Tuple

class WorldFetcher:
    """
    Fetches all necessary data from the world interface for analysis.
    """

    def __init__(self, terrain_loader: TerrainLoader):
        self.terrain = terrain_loader

    def fetch_build_area(self) -> BuildArea:
        """
        Determine build area from the world interface. 
        Returns:
            BuildArea
        """
        return self.terrain.get_build_area()

    def fetch_heightmaps(self, build_area: BuildArea) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Fetch heightmaps for the full build area.

        Returns:
            surface, ground, ocean_floor, plant_thickness 
            (all np.ndarray of shape [width, depth])
        """
        
        x = build_area.x_from
        z = build_area.z_from
        w = build_area.width
        d = build_area.depth

        surface = np.array(
            self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING")
        )

        ground = np.array(
            self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING_NO_PLANTS")
        )

        ocean_floor = np.array(
            self.terrain.get_heightmap(x, z, w, d, "OCEAN_FLOOR")
        )

        return surface, ground, ocean_floor, surface - ground
    
    def fetch_biomes(self, build_area: BuildArea) -> np.ndarray:
        """
        Fetch biome data for the build area, resized to match build area dimensions.
        
        Returns:
            np.ndarray of shape [width, depth], indexed by [x, z]
        """
        data = self.terrain.get_biomes(
            build_area.x_from,
            build_area.z_from,
            build_area.width,
            build_area.depth,
            )

        # If only 1D, make 2D
        if data.ndim == 1:
            data = data.reshape((1, -1))

        # Repeat array to match heightmap size
        reps_x = build_area.width  // data.shape[0] + 1
        reps_z = build_area.depth  // data.shape[1] + 1
        data = np.tile(data, (reps_x, reps_z))

        # Trim to exact dimensions
        data = data[:build_area.width, :build_area.depth]

        return data