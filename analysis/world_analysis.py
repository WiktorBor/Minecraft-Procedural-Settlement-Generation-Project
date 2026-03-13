from data.build_area import BuildArea
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from scipy.ndimage import distance_transform_edt, label, uniform_filter, generic_filter, sum as ndi_sum
import numpy as np

class WorldAnalyser:
    """
    Analyse a Minecraft world build area and compute the best location
    for building a settlement based on terrain, water, flatness and biome.
    The best area is dinamically sized to fit the largest high-scoring patch.
    Only 'prepare()' should be called from outside, which runs the full analysis and sets 'best_area'.
    """
    def __init__(self, terrain_loader):
        self.terrain = terrain_loader
        self.configuration = TerrainConfig()

    def prepare(self) -> WorldAnalysisResult:
        self._fetch_build_area()
        self._fetch_heightmaps()
        self._fetch_biomes()
        self._get_best_location()

        return WorldAnalysisResult(
            build_area=self.build_area,
            best_area=self.best_area,
            heightmap_ground=self.heightmap_ground,
            heightmap_surface=self.heightmap_surface,
            heightmap_ocean_floor=self.heightmap_ocean_floor,
            roughness_map=self.roughness_map,
            plant_thickness=self.plant_thickness,
            slope_map=self.slope_map,
            water_mask=self.water_mask,
            water_distances=self.water_distances,
            water_proximity=self.water_proximity,
            biomes=self.biomes,
            scores=self.scores
        )
    
    # FETCH FUNCTIONS
    def _fetch_build_area(self):
        """
        Determine build area from the world interface. 
        This is the area we will analyze for building suitability.
        """
        data = self.terrain.get_build_area()

        self.build_area = BuildArea(
            x_from = data["xFrom"],
            y_from = data["yFrom"],
            z_from = data["zFrom"],
            x_to = data["xTo"],
            y_to = data["yTo"],
            z_to = data["zTo"],
        )
        if self.build_area.width <= 0 or self.build_area.depth <= 0:
            raise ValueError("Build area has non-positive dimensions")
   
    def _fetch_heightmaps(self):
        """
        Fetch heightmaps for the full build area.
        """
        
        x = self.build_area.x_from
        z = self.build_area.z_from
        w = self.build_area.width
        d = self.build_area.depth

        self.heightmap_surface = np.array(
            self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING")
        )

        self.heightmap_ground = np.array(
            self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING_NO_PLANTS")
        )

        self.heightmap_ocean_floor = np.array(
            self.terrain.get_heightmap(x, z, w, d, "OCEAN_FLOOR")
        )

        # Compute plant thickness
        self.plant_thickness = self.heightmap_surface - self.heightmap_ground
    
    def _fetch_biomes(self):
        data = self.terrain.get_biomes(
            self.build_area.x_from,
            self.build_area.z_from,
            self.build_area.width,
            self.build_area.depth,
            )

        # If only 1D, make 2D
        if data.ndim == 1:
            data = data.reshape((1, -1))

        # Repeat array to match heightmap size
        reps_x = self.build_area.width  // data.shape[0] + 1
        reps_z = self.build_area.depth  // data.shape[1] + 1
        data = np.tile(data, (reps_x, reps_z))

        # Trim to exact dimensions
        data = data[:self.build_area.width, :self.build_area.depth]

        self.biomes = data


    def compute_slope_map(self):
        gx, gz = np.gradient(self.heightmap_ground)
        self.slope_map = np.sqrt(gx**2 + gz**2)
    
    def _build_water_mask(self):
        self.water_mask = self.heightmap_surface != self.heightmap_ocean_floor
        self.water_distances = distance_transform_edt(~self.water_mask)
    
    # Helper functions for scoring     
    def _compute_flatness(self, radius=5):
        size = 2 * radius + 1
        mean = uniform_filter(self.heightmap_ground, size=size)
        mean_sq = uniform_filter(self.heightmap_ground**2, size=size)

        variance = mean_sq - mean**2
        std = np.sqrt(np.maximum(variance, 0))

        return 1 / (1 + std)

    def _compute_accessibility(self):
        h = self.heightmap_ground

        up = np.abs(h - np.roll(h, -1, axis=0)) <= 1
        down = np.abs(h - np.roll(h, 1, axis=0)) <= 1
        left = np.abs(h - np.roll(h, -1, axis=1)) <= 1
        right = np.abs(h - np.roll(h, 1, axis=1)) <= 1

        return (up + down + left + right) / 4.0

    def _compute_expansion(self, radius=5):
        size = 2 * radius + 1
        base = self.heightmap_ground

        local_mean = uniform_filter(base, size=size)
        flat = np.abs(base - local_mean) <= 1

        return uniform_filter(flat.astype(float), size=size)

    def _compute_biome_score(self):

        lookup = np.vectorize(lambda b: TerrainConfig.biome_weights.get(b, 0.5))
        return lookup(self.biomes)
    
    def _compute_roughness(self, radius = 5):

        self.roughness_map = generic_filter(
            self.heightmap_ground,
            np.std,
            size=radius
        )

    # WORLD ANALYSER
    def _analyse(self):
        """Compute scores for all positions in the build area."""

        flatness = self._compute_flatness(radius=self.configuration.radius)
        access = self._compute_accessibility()
        self._build_water_mask()        
        self.water_proximity = (16 - np.minimum(self.water_distances, 16)) / 16
        expansion = self._compute_expansion(radius=self.configuration.radius)
        biome = self._compute_biome_score()
        self.compute_slope_map()

        forest_penalty = np.clip(self.plant_thickness / 5.0, 0, 1)
        slope_penalty = np.clip(self.slope_map / 3.0, 0, 1)

        water_penalty = self.water_mask.astype(float)
        water_proximity_bonus = self.water_proximity * (~self.water_mask).astype(float)

        max_h = np.max(self.heightmap_ground)
        elevation = self.heightmap_ground / max_h if max_h > 0 else np.zeros_like(self.heightmap_ground)
        self.scores = (
            1.5 * flatness +
            2.0 * access +
            2.0 * expansion +
            0.8 * water_proximity_bonus -
            1.0 * water_penalty +
            0.8 * elevation +
            0.5 * biome -
            2.0 * forest_penalty - 
            2.0 * slope_penalty
        )

    # GET BEST LOCATION
    def _get_best_location(self):
        """
        Pick the larges contiguous high-scoring patch of terrain.
        Iteratively lower the threshold if patch too small.
        """
        self._analyse()
        self._compute_roughness()

        # Build valid terrain mask
        valid_mask = (
            (self.slope_map <= 0.5) &
            (~self.water_mask) &
            (self.roughness_map <= 2)
        )

        if not np.any(valid_mask):
            raise ValueError("No valid build locations found.")

        valid_scores = self.scores[valid_mask]
        k = max(int(valid_scores.size * 0.25), 1)

        flat_scores = self.scores.ravel()
        flat_valid = valid_mask.ravel()
        valid_indices = np.where(flat_valid)[0]

        top_valid = np.argpartition(valid_scores, -k)[-k:]
        top_indices = valid_indices[top_valid]

        high_score_mask = np.zeros_like(flat_scores, dtype=bool)
        high_score_mask.ravel()[top_indices] = True
        high_score_mask = high_score_mask.reshape(self.scores.shape)

        candidate_mask = valid_mask & high_score_mask

        labeled, num_features = label(candidate_mask)
        if num_features == 0:
            raise ValueError("No contiguous build locations found.")
        
        region_sizes = ndi_sum(
            candidate_mask,
            labeled,
            index=np.arange(1, num_features + 1)
        )
        MIN_PATCH_SIZE = TerrainConfig.min_patch_size

        valid_labels = np.where(region_sizes >= MIN_PATCH_SIZE)[0] + 1

        if len(valid_labels) == 0:
            raise ValueError("No sufficiently large build locations found.")

        best_label = None
        best_score = -np.inf

        for label_id in valid_labels:

            region = np.argwhere(labeled == label_id)
            area = len(region)

            x_min, z_min = region.min(axis=0)
            x_max, z_max = region.max(axis=0)

            box_area = (x_max - x_min + 1) * (z_max - z_min + 1)

            compactness = area / box_area

            mean_score = np.mean(self.scores[labeled == label_id])

            final_score = mean_score * compactness * area

            if final_score > best_score:
                best_score = final_score
                best_label = label_id
        
        best_zone = np.argwhere(labeled == best_label)

        x_min, z_min = best_zone.min(axis=0)
        x_max, z_max = best_zone.max(axis=0)

        region_heights = self.heightmap_ground[x_min:x_max+1, z_min:z_max+1]
        y_min = int(region_heights.min())
        y_max = int(region_heights.max())

        self.best_area = BuildArea(
            x_min + self.build_area.x_from,
            y_min,
            z_min + self.build_area.z_from,
            x_max + self.build_area.x_from,
            y_max,
            z_max + self.build_area.z_from
        )