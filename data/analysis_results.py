from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from data.build_area import BuildArea


@dataclass
class WorldAnalysisResult:
    """
    Container for all world-analysis outputs consumed by planners.

    All numpy arrays are [x, z] indexed and share the shape
    (best_area.width, best_area.depth).

    Array dtypes
    ------------
    heightmap_ground      : int32   — Y level of the topmost solid block
    heightmap_surface     : int32   — Y level of the topmost non-air block
    heightmap_ocean_floor : int32   — Y level of the ocean floor
    roughness_map         : float32 — local height range within a neighbourhood
    slope_map             : float32 — local slope magnitude (np.gradient output)
    surface_blocks        : object  — surface block ID string per cell
    water_mask            : bool    — True where the cell is water
    biomes                : int32   — Minecraft biome ID per cell
    scores                : float32 — composite suitability score in [0, 1]

    Optional arrays (may not be computed in all analysis modes)
    -----------------------------------------------------------
    plant_thickness : float32 — vegetation density in [0, 1]
    water_distances : float32 — distance to nearest water cell (cells)
    """

    best_area:             BuildArea
    surface_blocks:        np.ndarray

    # Required maps
    heightmap_ground:      np.ndarray
    heightmap_surface:     np.ndarray
    heightmap_ocean_floor: np.ndarray
    roughness_map:         np.ndarray
    slope_map:             np.ndarray
    water_mask:            np.ndarray
    biomes:                np.ndarray
    scores:                np.ndarray

    # Optional maps
    plant_thickness: np.ndarray | None = field(default=None)
    water_distances: np.ndarray | None = field(default=None)

    def __post_init__(self) -> None:
        expected = (self.best_area.width, self.best_area.depth)

        required = {
            "heightmap_ground":      self.heightmap_ground,
            "heightmap_surface":     self.heightmap_surface,
            "heightmap_ocean_floor": self.heightmap_ocean_floor,
            "roughness_map":         self.roughness_map,
            "slope_map":             self.slope_map,
            "surface_blocks":        self.surface_blocks,
            "water_mask":            self.water_mask,
            "biomes":                self.biomes,
            "scores":                self.scores,
        }
        for name, arr in required.items():
            if not isinstance(arr, np.ndarray):
                raise TypeError(f"{name} must be a numpy array, got {type(arr)}")
            if arr.shape != expected:
                raise ValueError(
                    f"{name} has shape {arr.shape}, expected {expected}"
                )

        for name, arr in [
            ("plant_thickness", self.plant_thickness),
            ("water_distances", self.water_distances),
        ]:
            if arr is not None and arr.shape != expected:
                raise ValueError(
                    f"{name} has shape {arr.shape}, expected {expected}"
                )