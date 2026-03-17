import numpy as np
from scipy.ndimage import distance_transform_edt, uniform_filter, generic_filter
from data.configurations import TerrainConfig

class TerrainAnalyser:
    """
    Computes terrain metrics for settlement suitability.
    """
    def __init__(
            self, 
            heightmap_ground: np.ndarray, 
            heightmap_surface: np.ndarray, 
            heightmap_ocean_floor: np.ndarray, 
            biomes: np.ndarray,
            config: TerrainConfig
    ):
        self.heightmap_ground = heightmap_ground
        self.heightmap_surface = heightmap_surface
        self.heightmap_ocean_floor = heightmap_ocean_floor
        self.biomes = biomes
        self.config = config

        # Analysis outputs
        self.slope_map: np.ndarray = None
        self.flatness: np.ndarray = None
        self.accessibility: np.ndarray = None
        self.expansion: np.ndarray = None
        self.biome_score: np.ndarray = None
        self.water_mask: np.ndarray = None
        self.water_distances: np.ndarray = None
        self.roughness_map: np.ndarray = None
        self.scores: np.ndarray = None

    def compute_slope(self) -> None:
        gx, gz = np.gradient(self.heightmap_ground)
        self.slope_map = np.sqrt(gx**2 + gz**2)

    def compute_flatness(self) -> None:
        size = 2 * self.config.radius + 1
        mean = uniform_filter(self.heightmap_ground, size=size)
        mean_sq = uniform_filter(self.heightmap_ground**2, size=size)
        variance = mean_sq - mean**2
        self.flatness = 1 / (1 + np.sqrt(np.maximum(variance, 0)))

    def compute_accessibility(self) -> None:
        h = self.heightmap_ground
        up = np.abs(h - np.roll(h, -1, axis=0)) <= 1
        down = np.abs(h - np.roll(h, 1, axis=0)) <= 1
        left = np.abs(h - np.roll(h, -1, axis=1)) <= 1
        right = np.abs(h - np.roll(h, 1, axis=1)) <= 1
        self.accessibility = (up + down + left + right) / 4.0

    def compute_expansion(self) -> None:
        size = 2 * self.config.radius + 1
        base = self.heightmap_ground
        local_mean = uniform_filter(base, size=size)
        flat = np.abs(base - local_mean) <= 1
        self.expansion = uniform_filter(flat.astype(float), size=size)

    def compute_biome_score(self) -> None:
        lookup = np.vectorize(lambda b: self.config.biome_weights.get(b, 0.5))
        self.biome_score = lookup(self.biomes)

    def compute_water_mask(self) -> None:
        self.water_mask = self.heightmap_surface != self.heightmap_ocean_floor
        self.water_distances = distance_transform_edt(~self.water_mask)

    def compute_roughness(self) -> None:
        self.roughness_map = generic_filter(
            self.heightmap_ground,
            lambda x: np.max(x) - np.min(x),
            size=2 * self.config.radius + 1
        )

    def compute_scores(self) -> None:
        """
        Compute all analysis metrics and a combined score map.
        """
        self.compute_slope()
        self.compute_flatness()
        self.compute_accessibility()
        self.compute_expansion()
        self.compute_biome_score()
        self.compute_water_mask()
        self.compute_roughness()

        water_proximity_bonus = ((16 - np.minimum(self.water_distances, 16)) / 16) * (~self.water_mask).astype(float)

        forest_penalty = np.clip((self.heightmap_surface - self.heightmap_ground) / self.config.forest_scale, 0, 1)
        slope_penalty = np.clip(self.slope_map / self.config.slope_scale, 0, 1)
        water_penalty = self.water_mask.astype(float)

        max_h = np.max(self.heightmap_ground)
        elevation = self.heightmap_ground / max_h if max_h > 0 else np.zeros_like(self.heightmap_ground)

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