from __future__ import annotations

import numpy as np
from scipy.ndimage import label as ndimage_label, sum as ndi_sum, binary_dilation
from data.configurations import TerrainConfig
from data.build_area import BuildArea


class PatchSelector:
    """
    Selects the best contiguous patch of buildable land based on terrain
    scores and physical constraints (slope, water, roughness).
    """

    def __init__(
        self,
        build_area: BuildArea,
        scores: np.ndarray,
        slope_map: np.ndarray,
        water_mask: np.ndarray,
        roughness_map: np.ndarray,
        heightmap_ground: np.ndarray,
        config: TerrainConfig,
    ) -> None:
        self.build_area    = build_area
        self.scores        = scores
        self.slope_map     = slope_map
        self.water_mask    = water_mask
        self.roughness_map = roughness_map
        self.heightmap     = heightmap_ground
        self.config        = config

    def select_best_patch(self) -> BuildArea:
        """
        Select the best sub-area (BuildArea) for settlement placement.

        Raises
        ------
        ValueError
            If no patch meets the terrain constraints or minimum size.
        """
        cfg = self.config

        # ------------------------------------------------------------------
        # FIX 1 — Tolerant thresholds so a second run (where the first run's
        # structures slightly raised roughness of a few cells) doesn't
        # fragment the only valid region below min_patch_size.
        #
        # We try three passes in decreasing strictness:
        #   Pass A: original thresholds
        #   Pass B: 1.5× relaxed slope + roughness
        #   Pass C: roughness dropped entirely (slope only)
        # ------------------------------------------------------------------
        valid_mask = None
        for slope_mult, rough_mult in [(1.0, 1.0), (1.5, 1.5), (1.5, None)]:
            slope_ok = self.slope_map <= cfg.max_slope * slope_mult
            if rough_mult is not None:
                rough_ok = self.roughness_map <= cfg.max_roughness * rough_mult
            else:
                rough_ok = np.ones_like(slope_ok)

            candidate = slope_ok & (~self.water_mask) & rough_ok
            if np.any(candidate):
                valid_mask = candidate
                break

        if valid_mask is None or not np.any(valid_mask):
            raise ValueError("No valid build locations found.")

        # ------------------------------------------------------------------
        # FIX 2 — Penalise water-adjacent cells so the selector stops
        # choosing shoreline areas that appear flat only because of water.
        #
        # Any land cell within 3 blocks of water gets its score halved.
        # This leaves valid_mask unchanged (we still consider those cells),
        # but they score worse so inland regions win.
        # ------------------------------------------------------------------
        water_buffer  = binary_dilation(
            self.water_mask,
            iterations=cfg.water_proximity_penalty_cells,
        )
        near_water      = water_buffer & valid_mask
        adjusted_scores = self.scores.copy().astype(np.float64)
        adjusted_scores[near_water] *= cfg.water_proximity_score_mult

        # ------------------------------------------------------------------
        # FIX 3 — top-scoring cell selection now uses adjusted_scores
        # ------------------------------------------------------------------
        valid_scores  = adjusted_scores[valid_mask]
        k             = max(int(valid_scores.size * cfg.top_building_score_percentile), 1)

        flat_adj      = adjusted_scores.ravel()
        valid_indices = np.where(valid_mask.ravel())[0]
        top_valid     = np.argpartition(valid_scores, -k)[-k:]
        top_indices   = valid_indices[top_valid]

        high_score_mask = np.zeros(flat_adj.size, dtype=bool)
        high_score_mask[top_indices] = True
        high_score_mask = high_score_mask.reshape(adjusted_scores.shape)

        candidate_mask = valid_mask & high_score_mask

        # --- connected-component labelling ---
        labeled, num_features = ndimage_label(candidate_mask)
        if num_features == 0:
            raise ValueError("No contiguous build locations found.")

        label_index  = np.arange(1, num_features + 1)
        region_sizes = ndi_sum(candidate_mask, labeled, index=label_index)
        valid_labels = label_index[np.asarray(region_sizes) >= cfg.min_patch_size]

        if len(valid_labels) == 0:
            raise ValueError("No sufficiently large build locations found.")

        # ------------------------------------------------------------------
        # FIX 4 — Final score formula no longer multiplies by raw valid_sizes.
        #
        # Old:  final = mean_score * compactness * size
        #   → enormous water-adjacent regions always win on size alone.
        #
        # New:  final = mean_score * compactness * log(size)
        #   → size still matters (bigger is better), but logarithmically so
        #     a modestly-sized inland patch with a good mean score can beat
        #     a huge but mediocre shoreline blob.
        # ------------------------------------------------------------------
        region_score_sums = np.asarray(
            ndi_sum(adjusted_scores, labeled, index=valid_labels), dtype=np.float64
        )
        valid_sizes = np.asarray(region_sizes)[valid_labels - 1]
        mean_scores = region_score_sums / valid_sizes

        # Compactness: fill-ratio of bounding box
        compactness = np.empty(len(valid_labels), dtype=np.float64)
        for i, lid in enumerate(valid_labels):
            region = np.argwhere(labeled == lid)
            x_min, z_min = region.min(axis=0)
            x_max, z_max = region.max(axis=0)
            box_area     = (x_max - x_min + 1) * (z_max - z_min + 1)
            compactness[i] = valid_sizes[i] / box_area

        # log(size) prevents huge mediocre regions from dominating
        final_scores = mean_scores * compactness * np.log1p(valid_sizes)
        best_idx     = int(np.argmax(final_scores))
        best_label   = valid_labels[best_idx]

        # --- extract bounding box of best region ---
        best_zone    = np.argwhere(labeled == best_label)
        x_min, z_min = int(best_zone.min(axis=0)[0]), int(best_zone.min(axis=0)[1])
        x_max, z_max = int(best_zone.max(axis=0)[0]), int(best_zone.max(axis=0)[1])

        # --- enforce minimum bounding box dimensions from TerrainConfig ---
        map_w, map_d = self.heightmap.shape
        min_w = cfg.min_best_area_width
        min_d = cfg.min_best_area_depth

        def _expand(lo: int, hi: int, target: int, limit: int) -> tuple[int, int]:
            """Expand [lo, hi] to span at least `target` cells, clamped to [0, limit-1]."""
            if hi - lo + 1 >= target:
                return lo, hi
            centre = (lo + hi) // 2
            half   = target // 2
            lo     = max(0, centre - half)
            hi     = min(limit - 1, lo + target - 1)
            lo     = max(0, hi - target + 1)
            return lo, hi

        x_min, x_max = _expand(x_min, x_max, min_w, map_w)
        z_min, z_max = _expand(z_min, z_max, min_d, map_d)

        region_heights           = self.heightmap[x_min:x_max + 1, z_min:z_max + 1]
        y_min, y_max             = int(region_heights.min()), int(region_heights.max())
        world_x_min, world_z_min = self.build_area.index_to_world(x_min, z_min)
        world_x_max, world_z_max = self.build_area.index_to_world(x_max, z_max)

        return BuildArea(world_x_min, y_min, world_z_min,
                         world_x_max, y_max, world_z_max)