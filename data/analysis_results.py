from dataclasses import dataclass
import numpy as np
from .build_area import BuildArea

@dataclass
class WorldAnalysisResult:
    """
    Container for all analysis results of the world, to be used by planners.
    All np.ndarrays grids are [x, z] indexed and correspond to the build area.
    """
    best_area: BuildArea

    # shape: [width, depth]
    heightmap_ground: np.ndarray
    heightmap_surface: np.ndarray
    heightmap_ocean_floor: np.ndarray
    roughness_map: np.ndarray
    plant_thickness: np.ndarray
    slope_map: np.ndarray
    water_mask: np.ndarray
    water_distances: np.ndarray
    biomes: np.ndarray
    scores: np.ndarray