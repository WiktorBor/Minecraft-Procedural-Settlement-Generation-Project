from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from .build_area import BuildArea


@dataclass
class WorldAnalysisResult:
    """
    Immutable container for all world-analysis outputs consumed by planners.

    All numpy arrays are [x, z] indexed and share the shape
    (best_area.width, best_area.depth).

    Array dtypes
    ------------
    heightmap_ground      : int32   – Y level of the topmost solid block
    heightmap_surface     : int32   – Y level of the topmost non-air block
    heightmap_ocean_floor : int32   – Y level of the ocean floor
    roughness_map         : float32 – local terrain roughness in [0, 1]
    slope_map             : float32 – local slope magnitude in [0, 1]
    plant_thickness       : float32 – vegetation density in [0, 1]
    water_mask            : bool    – True where the cell is water
    water_distances       : float32 – distance to nearest water cell (cells)
    biomes                : int32   – Minecraft biome ID per cell
    scores                : float32 – composite suitability score in [0, 1]
    """

    best_area: BuildArea

    # -- required maps -------------------------------------------------------
    heightmap_ground:      np.ndarray
    heightmap_surface:     np.ndarray
    heightmap_ocean_floor: np.ndarray
    roughness_map:         np.ndarray
    slope_map:             np.ndarray
    water_mask:            np.ndarray
    biomes:                np.ndarray
    scores:                np.ndarray

    # -- optional maps (may not be computed in all analysis modes) -----------
    plant_thickness:  np.ndarray | None = field(default=None)
    water_distances:  np.ndarray | None = field(default=None)

    def __post_init__(self) -> None:
        expected = (self.best_area.width, self.best_area.depth)
        required = {
            "heightmap_ground":      self.heightmap_ground,
            "heightmap_surface":     self.heightmap_surface,
            "heightmap_ocean_floor": self.heightmap_ocean_floor,
            "roughness_map":         self.roughness_map,
            "slope_map":             self.slope_map,
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

        # Validate optional arrays if provided
        for name, arr in [
            ("plant_thickness", self.plant_thickness),
            ("water_distances", self.water_distances),
        ]:
            if arr is not None and arr.shape != expected:
                raise ValueError(
                    f"{name} has shape {arr.shape}, expected {expected}"
                )