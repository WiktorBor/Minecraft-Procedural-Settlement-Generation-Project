from dataclasses import dataclass
import numpy as np
from .build_area import BuildArea

@dataclass
class WorldAnalysisResult:
    build_area: BuildArea
    best_area: BuildArea
    heightmap_ground: np.ndarray
    heightmap_surface: np.ndarray
    heightmap_ocean_floor: np.ndarray
    roughness_map: np.ndarray
    plant_thickness: np.ndarray
    slope_map: np.ndarray
    water_mask: np.ndarray
    water_distances: np.ndarray
    water_proximity: np.ndarray
    biomes: np.ndarray
    scores: np.ndarray