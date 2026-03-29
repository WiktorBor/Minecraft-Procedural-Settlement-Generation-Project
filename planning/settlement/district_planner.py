from __future__ import annotations

import logging
import math
import random

import numpy as np
from scipy.ndimage import label as ndlabel
from scipy.spatial import Voronoi, cKDTree

from ai.district_mdp import DistrictMDP, thresholds_from_terrain
from data.analysis_results import WorldAnalysisResult
from data.build_area import BuildArea
from data.configurations import SettlementConfig
from data.settlement_entities import District, Districts
from utils.poisson_disk import poisson_disk

logger = logging.getLogger(__name__)


class DistrictPlanner:
    """
    Voronoi-based district planner with MDP-driven type assignment.

    Seed count is derived automatically from the build-area size and a
    target district footprint (config.target_district_size), so the number
    of districts always reflects how many can comfortably fit.

    Districts smaller than min_structures_per_district × smallest plot are
    dropped after the Voronoi partition.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        config: SettlementConfig,
        num_districts: int | None = None,
        seed: int | None = None,
    ) -> None:
        self.analysis      = analysis
        self.config        = config
        self.num_districts = num_districts  # None → auto-fit from area
        self.seed          = seed

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self._mdp = DistrictMDP(gamma=0.9)
        self._mdp.solve(iterations=200)
        self._thresholds: dict = {}

        logger.info("District MDP solved.\n%s", self._mdp.policy_table())

    # ------------------------------------------------------------------

    def generate(self) -> Districts:
        area             = self.analysis.best_area
        local_slope      = self.analysis.slope_map
        local_roughness  = self.analysis.roughness_map
        local_water_dist = self.analysis.water_distances

        w, d = local_slope.shape
        total_cells = w * d

        # Compute terrain-relative MDP thresholds before type assignment
        self._thresholds = thresholds_from_terrain(
            local_slope, local_roughness, self.config
        )

        # Auto-fit seed count from area size
        if self.num_districts is not None:
            n_target = max(2, self.num_districts)
        else:
            min_structures = getattr(self.config, "min_structures_per_district", 3)
            smallest_plot  = (
                min(self.config.plot_width.values())
                * min(self.config.plot_depth.values())
            )
            min_viable    = smallest_plot * min_structures * 4
            config_size   = getattr(self.config, "target_district_size", min_viable)
            target_size   = max(config_size, min_viable)
            n_target      = max(2, total_cells // target_size)

        logger.info(
            "target_district_size used: %d cells → %d districts targeted",
            total_cells // max(1, n_target), n_target,
        )

        poisson_radius = math.sqrt(total_cells / (n_target * math.pi))
        poisson_radius = max(3.0, poisson_radius)

        logger.info(
            "Area %d×%d (%d cells) → targeting %d districts, Poisson radius=%.1f",
            w, d, total_cells, n_target, poisson_radius,
        )

        score = self._get_score_map(local_slope, local_roughness)

        seeds = poisson_disk(
            width=w,
            depth=d,
            radius=poisson_radius,
            score_map=score,
            seed=self.seed,
        )

        if len(seeds) < 2:
            logger.warning(
                "Poisson-disk returned only %d seed(s) — "
                "build area may be too small or radius too large. "
                "Falling back to a 2×2 grid of seeds.",
                len(seeds),
            )
            seeds = np.array([
                [w // 3,     d // 3    ],
                [w * 2 // 3, d // 3    ],
                [w // 3,     d * 2 // 3],
                [w * 2 // 3, d * 2 // 3],
            ], dtype=float)

        logger.info("Poisson-disk produced %d seeds.", len(seeds))

        vor  = Voronoi(seeds)
        tree = cKDTree(seeds)

        xi, zi  = np.indices((w, d))
        coords  = np.stack([xi.ravel(), zi.ravel()], axis=-1)
        _, district_map_flat = tree.query(coords)
        district_map = district_map_flat.reshape(w, d)

        n_seeds = len(seeds)

        counts        = np.bincount(district_map_flat, minlength=n_seeds)
        avg_slope     = np.zeros(n_seeds)
        avg_roughness = np.zeros(n_seeds)
        avg_water     = np.zeros(n_seeds)

        for i in range(n_seeds):
            if counts[i] == 0:
                continue
            mask = district_map == i
            avg_slope[i]     = float(np.mean(local_slope[mask]))
            avg_roughness[i] = float(np.mean(local_roughness[mask]))
            avg_water[i]     = float(np.mean(local_water_dist[mask]))

        min_structures = getattr(self.config, "min_structures_per_district", 3)
        smallest_w     = min(self.config.plot_width.values())
        smallest_d     = min(self.config.plot_depth.values())
        min_cells      = min_structures * smallest_w * smallest_d * 4

        valid_indices = [
            idx for idx in range(n_seeds) if counts[idx] >= min_cells
        ]

        if not valid_indices:
            logger.warning(
                "No districts passed the min-size filter (min_cells=%d, "
                "largest district=%d cells). Relaxing to largest 50%%.",
                min_cells, int(counts.max()),
            )
            median_count  = np.median(counts)
            valid_indices = [
                idx for idx in range(n_seeds) if counts[idx] >= median_count
            ]

        logger.info(
            "%d of %d Voronoi regions kept after size filter (min %d cells).",
            len(valid_indices), n_seeds, min_cells,
        )

        final_map           = np.full_like(district_map, -1)
        final_district_list: list[District]  = []
        final_district_types: dict[int, str] = {}

        for new_idx, old_idx in enumerate(valid_indices):
            final_map[district_map == old_idx] = new_idx

            dtype = self._assign_type(
                avg_slope[old_idx],
                avg_roughness[old_idx],
                avg_water[old_idx],
            )

            mask_coords      = np.argwhere(district_map == old_idx)
            x_min, z_min     = mask_coords.min(axis=0)
            x_max, z_max     = mask_coords.max(axis=0)
            wx_corner, wz_corner = area.index_to_world(int(x_min), int(z_min))

            d_obj = District(
                x     = wx_corner,
                z     = wz_corner,
                width = int(x_max - x_min + 1),
                depth = int(z_max - z_min + 1),
                type  = dtype,
            )
            final_district_list.append(d_obj)
            final_district_types[new_idx] = dtype

            logger.debug(
                "  District %d: type=%-12s  corner=(%d,%d)  size=%dx%d  cells=%d",
                new_idx, dtype, wx_corner, wz_corner,
                d_obj.width, d_obj.depth, counts[old_idx],
            )

        logger.info("Generated %d districts.", len(final_district_list))

        final_map, final_district_list, final_district_types, seeds_final = \
            self._merge_connected_same_type(
                final_map,
                final_district_list,
                final_district_types,
                seeds[valid_indices],
                area,
            )

        return Districts(
            map          = final_map,
            types        = final_district_types,
            seeds        = seeds_final,
            voronoi      = vor,
            district_list= final_district_list,
        )

    # ------------------------------------------------------------------

    def _assign_type(self, slope: float, roughness: float, water_dist: float) -> str:
        return self._mdp.act(slope, roughness, water_dist, **self._thresholds)

    def _get_score_map(
        self, slope: np.ndarray, roughness: np.ndarray
    ) -> np.ndarray:
        s_norm = 1.0 - np.clip(
            slope     / max(float(self.config.max_slope),     1e-5), 0.0, 1.0
        )
        r_norm = 1.0 - np.clip(
            roughness / max(float(self.config.max_roughness), 1e-5), 0.0, 1.0
        )
        return s_norm * 0.7 + r_norm * 0.3

    def _merge_connected_same_type(
        self,
        final_map: np.ndarray,
        final_district_list: list[District],
        final_district_types: dict[int, str],
        seeds: np.ndarray,
        area: BuildArea,
    ) -> tuple[np.ndarray, list[District], dict[int, str], np.ndarray]:
        """
        Merge only physically contiguous (4-connected) Voronoi cells of the
        same district type into a single District object.

        Uses scipy.ndimage.label for flood-fill connected-component labelling
        per type, so two patches of "residential" on opposite sides of the map
        remain separate districts even though they share a type.
        """
        if len(final_district_list) == 0:
            return final_map, final_district_list, final_district_types, seeds

        all_types = set(final_district_types.values())
        new_map = np.full_like(final_map, -1)
        new_district_list:  list[District]  = []
        new_district_types: dict[int, str]  = {}
        new_seeds_list:     list[np.ndarray] = []
        new_idx = 0

        # 4-connectivity kernel (no diagonals — strict physical adjacency)
        struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.int32)

        min_structures = getattr(self.config, "min_structures_per_district", 3)
        smallest_w     = min(self.config.plot_width.values())
        smallest_d     = min(self.config.plot_depth.values())
        min_cells      = min_structures * smallest_w * smallest_d * 4

        for dtype in sorted(all_types):
            type_mask = np.zeros(final_map.shape, dtype=bool)
            for vid, vtype in final_district_types.items():
                if vtype == dtype:
                    type_mask |= (final_map == vid)

            if not type_mask.any():
                continue

            labeled, n_components = ndlabel(type_mask, structure=struct)

            for comp_id in range(1, n_components + 1):
                comp_mask  = labeled == comp_id
                cell_count = int(comp_mask.sum())

                if cell_count < min_cells:
                    logger.debug(
                        "Dropping small connected component of type '%s' "
                        "(%d cells < %d min).",
                        dtype, cell_count, min_cells,
                    )
                    continue

                new_map[comp_mask] = new_idx

                cell_coords    = np.argwhere(comp_mask)
                centroid_local = cell_coords.mean(axis=0)
                x_min, z_min   = cell_coords.min(axis=0)
                x_max, z_max   = cell_coords.max(axis=0)
                wx_min, wz_min = area.index_to_world(int(x_min), int(z_min))

                d_obj = District(
                    x     = wx_min,
                    z     = wz_min,
                    width = int(x_max - x_min + 1),
                    depth = int(z_max - z_min + 1),
                    type  = dtype,
                )
                new_district_list.append(d_obj)
                new_district_types[new_idx] = dtype
                new_seeds_list.append(centroid_local.astype(np.float32))

                logger.info(
                    "Connected component %d: type=%-12s  cells=%d  "
                    "corner=(%d,%d)  size=%dx%d",
                    new_idx, dtype, cell_count,
                    wx_min, wz_min, d_obj.width, d_obj.depth,
                )
                new_idx += 1

        if not new_seeds_list:
            logger.warning(
                "_merge_connected_same_type: no components survived, "
                "returning originals."
            )
            return final_map, final_district_list, final_district_types, seeds

        new_seeds = np.array(new_seeds_list, dtype=np.float32)
        logger.info(
            "After connected-component merge: %d districts (was %d Voronoi regions).",
            len(new_district_list), len(final_district_list),
        )
        return new_map, new_district_list, new_district_types, new_seeds