from __future__ import annotations

import logging
import random

import numpy as np
from scipy.spatial import Voronoi

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_entities import District, Districts
from utils.poisson_disk import poisson_disk

logger = logging.getLogger(__name__)


class DistrictPlanner:
    """
    Voronoi-based district planner.

    Generates district seed points via Poisson-disk sampling weighted by
    terrain quality, builds a Voronoi partition, then assigns each district
    a type based on its average slope, roughness, and water proximity.
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
        self.num_districts = num_districts if num_districts is not None else config.num_districts
        self.seed          = seed

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def generate(self) -> Districts:
        """
        Generate districts within the best build area.

        Returns
        -------
        Districts
            Voronoi map, type assignments, seeds, Voronoi object, and
            a list of District objects in index order.
        """
        area = self.analysis.best_area
        logger.info("Generating %d districts...", self.num_districts)

        local_slope     = self.analysis.slope_map
        local_roughness = self.analysis.roughness_map
        local_water_dist = self.analysis.water_distances

        w, d = local_slope.shape

        # --- terrain-weighted score map for seed placement ---
        max_slope = max(float(local_slope.max()), 1e-5)
        max_rough = max(float(local_roughness.max()), 1e-5)

        score = np.clip(
            1.0
            - 0.5 * (local_slope / max_slope)
            - 0.3 * (local_roughness / max_rough),
            0.0, 1.0,
        )

        # --- Poisson-disk seed generation ---
        seeds = poisson_disk(
            width=w,
            height=d,
            radius=max(self.config.radius, min(w, d) / (self.num_districts * 2)),
            score_map=score,
            seed=self.seed,
        )

        if len(seeds) > self.num_districts:
            indices = np.random.choice(len(seeds), size=self.num_districts, replace=False)
            seeds   = seeds[indices]

        vor = Voronoi(seeds)

        # --- vectorised Voronoi map ---
        xs, zs    = np.meshgrid(np.arange(w), np.arange(d), indexing="ij")
        grid      = np.stack((xs, zs), axis=-1)                          # (w, d, 2)
        distances = np.sum((grid[..., None, :] - seeds) ** 2, axis=-1)  # (w, d, N)
        district_map: np.ndarray = np.argmin(distances, axis=-1).astype(np.int32)

        # --- per-district aggregations (fully vectorised) ---
        district_ids   = district_map.ravel()
        n              = self.num_districts
        counts         = np.maximum(np.bincount(district_ids, minlength=n), 1)

        avg_slope      = np.bincount(district_ids, weights=local_slope.ravel(),      minlength=n) / counts
        avg_roughness  = np.bincount(district_ids, weights=local_roughness.ravel(),  minlength=n) / counts
        avg_water_dist = np.bincount(district_ids, weights=local_water_dist.ravel(), minlength=n) / counts

        # Bounding boxes via vectorised scatter — avoids np.minimum/maximum.at loops
        xs_flat = xs.ravel().astype(np.int32)
        zs_flat = zs.ravel().astype(np.int32)

        x_min = np.full(n, w, dtype=np.int32)
        z_min = np.full(n, d, dtype=np.int32)
        x_max = np.zeros(n, dtype=np.int32)
        z_max = np.zeros(n, dtype=np.int32)

        np.minimum.at(x_min, district_ids, xs_flat)
        np.minimum.at(z_min, district_ids, zs_flat)
        np.maximum.at(x_max, district_ids, xs_flat)
        np.maximum.at(z_max, district_ids, zs_flat)

        # Centre of mass per district — computed from per-district sums (no argwhere loop)
        x_sum = np.bincount(district_ids, weights=xs_flat.astype(float), minlength=n) / counts
        z_sum = np.bincount(district_ids, weights=zs_flat.astype(float), minlength=n) / counts

        # --- assign types and build District objects ---
        district_types: dict[int, str] = {}
        district_list:  list[District] = []

        for idx in range(n):
            dtype = self._assign_type(
                avg_slope[idx],
                avg_roughness[idx],
                avg_water_dist[idx],
            )
            district_types[idx] = dtype

            wx, wz   = area.index_to_world(int(x_min[idx]), int(z_min[idx]))
            cx, cz   = area.index_to_world(int(x_sum[idx]), int(z_sum[idx]))
            width    = int(x_max[idx]) - int(x_min[idx]) + 1
            depth    = int(z_max[idx]) - int(z_min[idx]) + 1

            # District inherits x, z, width, depth from RectangularArea;
            # center_x / center_z are derived properties — no separate center field.
            d_obj = District(x=wx, z=wz, width=width, depth=depth, type=dtype)

            # Override centre to the computed centroid (not the bounding-box centre)
            # by adjusting x/z so that center_x == cx and center_z == cz.
            # Since center_x = x + width/2, we back-calculate x from the centroid.
            d_obj = District(
                x=int(cx - width / 2),
                z=int(cz - depth / 2),
                width=width,
                depth=depth,
                type=dtype,
            )

            district_list.append(d_obj)

        return Districts(
            map=district_map,
            types=district_types,
            seeds=vor.points,
            voronoi=vor,
            district_list=district_list,
        )

    def _assign_type(
        self,
        slope: float,
        roughness: float,
        water_dist: float,
    ) -> str:
        """
        Assign a district type from terrain metrics.

        Rule priority follows the order of keys in config.district_type_rules.
        'forest' is the default fallback if no rule matches.
        """
        for candidate, rules in self.config.district_type_rules.items():
            if candidate == "fishing":
                if water_dist <= rules.get("water_dist_max", np.inf):
                    return "fishing"

            elif candidate in ("farming", "residential"):
                if (slope     <= rules.get("slope_max",     np.inf) and
                        roughness <= rules.get("roughness_max", np.inf) and
                        random.random() < rules.get("probability", 0.5)):
                    return candidate

        return "forest"