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
        # Pass A/B/C: try progressively relaxed slope+roughness thresholds
        # so a second run (where previous structures raised roughness slightly)
        # doesn't fragment the only valid region below min_patch_size.
        # ------------------------------------------------------------------
        valid_mask = None
        for slope_mult, rough_mult in [(1.0, 1.0), (1.5, 1.5), (1.5, None)]:
            slope_ok = self.slope_map <= cfg.max_slope * slope_mult
            rough_ok = (
                self.roughness_map <= cfg.max_roughness * rough_mult
                if rough_mult is not None
                else np.ones_like(slope_ok)
            )
            candidate = slope_ok & (~self.water_mask) & rough_ok
            if np.any(candidate):
                valid_mask = candidate
                break

        if valid_mask is None or not np.any(valid_mask):
            raise ValueError("No valid build locations found.")

        # Penalise water-adjacent cells so inland regions beat shoreline blobs
        water_buffer    = binary_dilation(
            self.water_mask,
            iterations=cfg.water_proximity_penalty_cells,
        )
        near_water      = water_buffer & valid_mask
        adjusted_scores = self.scores.copy().astype(np.float64)
        adjusted_scores[near_water] *= cfg.water_proximity_score_mult

        # Top-k selection
        valid_scores  = adjusted_scores[valid_mask]
        k             = max(int(valid_scores.size * cfg.top_building_score_percentile), 1)
        valid_indices = np.where(valid_mask.ravel())[0]
        top_valid     = np.argpartition(valid_scores, -k)[-k:]
        top_indices   = valid_indices[top_valid]

        high_score_mask = np.zeros(adjusted_scores.size, dtype=bool)
        high_score_mask[top_indices] = True
        high_score_mask = high_score_mask.reshape(adjusted_scores.shape)

        candidate_mask = valid_mask & high_score_mask

        labeled, num_features = ndimage_label(candidate_mask)
        if num_features == 0:
            raise ValueError("No contiguous build locations found.")

        label_index  = np.arange(1, num_features + 1)
        region_sizes = ndi_sum(candidate_mask, labeled, index=label_index)
        valid_labels = label_index[np.asarray(region_sizes) >= cfg.min_patch_size]

        if len(valid_labels) == 0:
            raise ValueError("No sufficiently large build locations found.")

        region_score_sums = np.asarray(
            ndi_sum(adjusted_scores, labeled, index=valid_labels), dtype=np.float64
        )
        valid_sizes = np.asarray(region_sizes)[valid_labels - 1]
        mean_scores = region_score_sums / valid_sizes

        compactness = np.empty(len(valid_labels), dtype=np.float64)
        for i, lid in enumerate(valid_labels):
            region = np.argwhere(labeled == lid)
            x_min, z_min = region.min(axis=0)
            x_max, z_max = region.max(axis=0)
            box_area       = (x_max - x_min + 1) * (z_max - z_min + 1)
            compactness[i] = valid_sizes[i] / box_area

        final_scores = mean_scores * compactness * np.log1p(valid_sizes)

        # Sort best→worst so we can fall through to the next candidate
        # if the top patch fails the height-range buildability check.
        sorted_idx = np.argsort(final_scores)[::-1]

        map_w, map_d = self.heightmap.shape
        min_w = cfg.min_best_area_width
        min_d = cfg.min_best_area_depth

        def _expand(lo: int, hi: int, target: int, limit: int) -> tuple[int, int]:
            if hi - lo + 1 >= target:
                return lo, hi
            centre = (lo + hi) // 2
            half   = target // 2
            lo     = max(0, centre - half)
            hi     = min(limit - 1, lo + target - 1)
            lo     = max(0, hi - target + 1)
            return lo, hi

        x_min = z_min = x_max = z_max = 0
        best_label = None

        for idx in sorted_idx:
            label = valid_labels[idx]
            zone  = np.argwhere(labeled == label)
            lx_min = int(zone[:, 0].min())
            lz_min = int(zone[:, 1].min())
            lx_max = int(zone[:, 0].max())
            lz_max = int(zone[:, 1].max())

            # Expand to minimum dimensions before height check
            lx_min, lx_max = _expand(lx_min, lx_max, min_w, map_w)
            lz_min, lz_max = _expand(lz_min, lz_max, min_d, map_d)

            region_h = self.heightmap[lx_min:lx_max + 1, lz_min:lz_max + 1]
            h_range  = int(region_h.max()) - int(region_h.min())

            # Case 1: height range acceptable — check water coverage then accept
            if h_range <= cfg.max_height_range:
                region_water = self.water_mask[lx_min:lx_max + 1, lz_min:lz_max + 1]
                water_frac   = float(region_water.sum()) / region_water.size
                if water_frac <= cfg.max_water_fraction:
                    best_label = label
                    x_min, z_min, x_max, z_max = lx_min, lz_min, lx_max, lz_max
                    break
                # Too much water — fall through to case 2 or next label

            # Case 2: too steep — check if the largest flat sub-patch inside
            # this box is still large enough to contain the settlement.
            modal_y  = int(
                np.bincount(
                    region_h.ravel().astype(np.int32) - int(region_h.min())
                ).argmax()
            ) + int(region_h.min())
            flat_mask = np.abs(region_h - modal_y) <= cfg.max_height_range
            lab2, n2  = ndimage_label(flat_mask)
            if n2 == 0:
                continue

            sizes2 = np.array([int(np.sum(lab2 == i)) for i in range(1, n2 + 1)])
            best2  = int(np.argmax(sizes2)) + 1
            cells2 = np.argwhere(lab2 == best2)
            fw = int(cells2[:, 0].max() - cells2[:, 0].min() + 1)
            fd = int(cells2[:, 1].max() - cells2[:, 1].min() + 1)

            if fw >= min_w and fd >= min_d:
                # Flat sub-patch fits — check water coverage before accepting
                sub_ox = lx_min + int(cells2[:, 0].min())
                sub_oz = lz_min + int(cells2[:, 1].min())
                sx_min, sx_max = _expand(sub_ox, sub_ox + fw - 1, min_w, map_w)
                sz_min, sz_max = _expand(sub_oz, sub_oz + fd - 1, min_d, map_d)
                sub_water  = self.water_mask[sx_min:sx_max + 1, sz_min:sz_max + 1]
                water_frac = float(sub_water.sum()) / sub_water.size
                if water_frac <= cfg.max_water_fraction:
                    best_label = label
                    x_min, z_min, x_max, z_max = sx_min, sz_min, sx_max, sz_max
                    break

            # Doesn't fit or too much water — try the next best label

        if best_label is None:
            raise ValueError(
                "No patch found where the full settlement footprint fits "
                "within the allowed height range. Try increasing "
                "max_height_range in TerrainConfig."
            )

        region_heights           = self.heightmap[x_min:x_max + 1, z_min:z_max + 1]
        y_min, y_max             = int(region_heights.min()), int(region_heights.max())
        world_x_min, world_z_min = self.build_area.index_to_world(x_min, z_min)
        world_x_max, world_z_max = self.build_area.index_to_world(x_max, z_max)

        return BuildArea(world_x_min, y_min, world_z_min,
                         world_x_max, y_max, world_z_max)