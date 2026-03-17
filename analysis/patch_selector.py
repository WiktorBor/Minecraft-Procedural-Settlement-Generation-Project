import numpy as np
from scipy.ndimage import label, sum as ndi_sum
from data.configurations import TerrainConfig
from data.build_area import BuildArea

class PatchSelector:
    """
    Selects the best contiguous patch of land for building based on terrain scores and constraints.
    """
    def __init__(
            self, 
            build_area: BuildArea, 
            scores: np.ndarray, 
            slope_map: np.ndarray, 
            water_mask: np.ndarray, 
            roughness_map: np.ndarray,
            heightmap_ground: np.ndarray, 
            config: TerrainConfig
    ):
        self.build_area = build_area
        self.scores = scores
        self.slope_map = slope_map
        self.water_mask = water_mask
        self.roughness_map = roughness_map
        self.heightmap = heightmap_ground
        self.config = config

    def select_best_patch(self) -> BuildArea:
        """
        Select the best sub-area (BuildArea) for settlement based on terrain metrics.
        """
        min_patch = self.config.min_patch_size

        valid_mask = (self.slope_map <= self.config.max_slope) & (~self.water_mask) & (self.roughness_map <= self.config.max_roughness)
        if not np.any(valid_mask):
            raise ValueError("No valid build locations found.")
        
        valid_scores = self.scores[valid_mask]
        k = max(int(valid_scores.size * self.config.top_building_score_percentile), 1)

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
            index=np.arange(1, num_features + 1))
        
        valid_labels = np.where(region_sizes >= min_patch)[0] + 1
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
        
        region_heights = self.heightmap[x_min:x_max+1, z_min:z_max+1]
        y_min, y_max = int(region_heights.min()), int(region_heights.max())
        
        world_x_min, world_z_min = self.build_area.index_to_world(x_min, z_min)
        world_x_max, world_z_max = self.build_area.index_to_world(x_max, z_max)
        
        return BuildArea(world_x_min, y_min, world_z_min,
                         world_x_max, y_max, world_z_max)