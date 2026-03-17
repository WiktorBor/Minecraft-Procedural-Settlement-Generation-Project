from __future__ import annotations

import numpy as np
from scipy.ndimage import (
    distance_transform_edt,
    uniform_filter,
    maximum_filter,
    minimum_filter,
)
from data.configurations import TerrainConfig


class TerrainAnalyser:
    """
    Computes terrain metrics for settlement suitability scoring.

    Usage
    -----
    Call `compute_scores()` as the single public entry point — it runs all
    metrics in the correct order and populates every output attribute.
    Individual `_compute_*` methods are private implementation details.
    """

    def __init__(
        self,
        heightmap_ground: np.ndarray,
        heightmap_surface: np.ndarray,
        heightmap_ocean_floor: np.ndarray,
        biomes: np.ndarray,
        config: TerrainConfig,
    ) -> None:
        self.heightmap_ground = heightmap_ground.astype(np.float32, copy=False)
        self.heightmap_surface = heightmap_surface.astype(np.float32, copy=False)
        self.heightmap_ocean_floor = heightmap_ocean_floor.astype(np.float32, copy=False)
        self.biomes = biomes
        self.config = config

        # Analysis outputs — populated by compute_scores()
        self.slope_map:      np.ndarray | None = None
        self.flatness:       np.ndarray | None = None
        self.accessibility:  np.ndarray | None = None
        self.expansion:      np.ndarray | None = None
        self.biome_score:    np.ndarray | None = None
        self.water_mask:     np.ndarray | None = None
        self.water_distances: np.ndarray | None = None
        self.roughness_map:  np.ndarray | None = None
        self.scores:         np.ndarray | None = None

    # Private metric computations

    def _compute_slope(self) -> None:
        gx, gz = np.gradient(self.heightmap_ground)
        self.slope_map = np.sqrt(gx ** 2 + gz ** 2)

    def _compute_flatness(self) -> None:
        size = 2 * self.config.radius + 1
        mean = uniform_filter(self.heightmap_ground, size=size)
        mean_sq = uniform_filter(self.heightmap_ground ** 2, size=size)
        variance = mean_sq - mean ** 2
        self.flatness = 1.0 / (1.0 + np.sqrt(np.maximum(variance, 0)))

    def _compute_accessibility(self) -> None:
        """
        Fraction of 4-neighbours reachable with at most 1 block height step.
        Uses slicing instead of np.roll to avoid wrap-around artefacts at edges.
        """
        h = self.heightmap_ground
        w, d = h.shape
        acc = np.zeros((w, d), dtype=np.float32)

        # Interior comparisons — slice-based
        acc[:-1, :] += (np.abs(h[:-1, :] - h[1:, :]) <= 1).astype(np.float32)   # down
        acc[1:,  :] += (np.abs(h[1:,  :] - h[:-1, :]) <= 1).astype(np.float32)  # up
        acc[:, :-1] += (np.abs(h[:, :-1] - h[:, 1:]) <= 1).astype(np.float32)   # right
        acc[:, 1:]  += (np.abs(h[:, 1:]  - h[:, :-1]) <= 1).astype(np.float32)  # left

        # Normalise by actual neighbour count (corners have 2, edges 3, interior 4)
        neighbour_count = np.ones((w, d), dtype=np.float32) * 4
        neighbour_count[0,  :] -= 1
        neighbour_count[-1, :] -= 1
        neighbour_count[:,  0] -= 1
        neighbour_count[:, -1] -= 1

        self.accessibility = acc / neighbour_count

    def _compute_expansion(self) -> None:
        size = 2 * self.config.radius + 1
        local_mean = uniform_filter(self.heightmap_ground, size=size)
        flat = (np.abs(self.heightmap_ground - local_mean) <= 1).astype(np.float32)
        self.expansion = uniform_filter(flat, size=size)

    def _compute_biome_score(self) -> None:
        """
        Map biome string array to float scores using a vectorised unique-lookup.
        """
        unique_biomes, inverse = np.unique(self.biomes, return_inverse=True)
        weights = np.array(
            [self.config.biome_weights.get(b, 0.5) for b in unique_biomes],
            dtype=np.float32,
        )
        self.biome_score = weights[inverse].reshape(self.biomes.shape)

    def _compute_water(self) -> None:
        """
        Identify water cells and compute distance to nearest water for each cell.
        """
        self.water_mask = self.heightmap_surface != self.heightmap_ocean_floor
        self.water_distances = distance_transform_edt(~self.water_mask).astype(np.float32)

    def _compute_roughness(self) -> None:
        """
        Local height range using C-level max/min filters for efficiency.
        """
        size = 2 * self.config.radius + 1
        self.roughness_map = (
            maximum_filter(self.heightmap_ground, size=size) -
            minimum_filter(self.heightmap_ground, size=size)
        )

    # Public entry point

    def compute_scores(self) -> None:
        """
        Compute all terrain metrics and a combined suitability score map.
        This is the only method that should be called externally.
        """
        self._compute_slope()
        self._compute_flatness()
        self._compute_accessibility()
        self._compute_expansion()
        self._compute_biome_score()
        self._compute_water()
        self._compute_roughness()

        water_proximity_bonus = (
            (16 - np.minimum(self.water_distances, 16)) / 16
        ) * (~self.water_mask).astype(np.float32)

        forest_penalty = np.clip(
            (self.heightmap_surface - self.heightmap_ground) / self.config.forest_scale,
            0, 1,
        )
        slope_penalty  = np.clip(self.slope_map / self.config.slope_scale, 0, 1)
        water_penalty  = self.water_mask.astype(np.float32)

        max_h = float(np.max(self.heightmap_ground))
        elevation = (
            self.heightmap_ground / max_h if max_h > 0
            else np.zeros_like(self.heightmap_ground)
        )

        self.scores = (
            1.5 * self.flatness +
            2.0 * self.accessibility +
            2.0 * self.expansion +
            0.5 * self.biome_score +
            0.8 * elevation +
            0.8 * water_proximity_bonus -
            1.0 * water_penalty -
            2.0 * forest_penalty -
            2.0 * slope_penalty
        )