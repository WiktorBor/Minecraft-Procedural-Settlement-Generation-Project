from __future__ import annotations

import logging
import random

import numpy as np
from scipy.spatial import Voronoi

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_entities import District, Districts
from utils.poisson_disk import poisson_disk
from ai.district_mdp import DistrictMDP, thresholds_from_config

logger = logging.getLogger(__name__)


class DistrictPlanner:
    """
    Voronoi-based district planner with MDP-driven type assignment.

    Generates district seed points via Poisson-disk sampling weighted by
    terrain quality, builds a Voronoi partition, then assigns each district
    a type using a policy learned offline via value iteration on a small
    terrain-feature MDP (27 states × 4 actions).

    The MDP replaces the previous rule-cascade heuristic in _assign_type.
    It is solved once at construction time and adds negligible overhead.
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

        # --- MDP: solve once at construction, reuse for every district ---
        # Bin thresholds are derived from SettlementConfig so the MDP shares
        # the same domain numbers as the rest of the planner — single source
        # of truth, and straightforward to document in a report.
        self._mdp = DistrictMDP(gamma=0.9)
        self._mdp.solve(iterations=200)
        self._thresholds = thresholds_from_config(config)
        logger.info("District MDP solved.\n%s", self._mdp.policy_table())

    # ------------------------------------------------------------------

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

        local_slope      = self.analysis.slope_map
        local_roughness  = self.analysis.roughness_map
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
        grid      = np.stack((xs, zs), axis=-1)
        distances = np.sum((grid[..., None, :] - seeds) ** 2, axis=-1)
        district_map: np.ndarray = np.argmin(distances, axis=-1).astype(np.int32)

        # --- per-district aggregations ---
        district_ids   = district_map.ravel()
        n              = self.num_districts
        counts         = np.maximum(np.bincount(district_ids, minlength=n), 1)

        avg_slope      = np.bincount(district_ids, weights=local_slope.ravel(),      minlength=n) / counts
        avg_roughness  = np.bincount(district_ids, weights=local_roughness.ravel(),  minlength=n) / counts
        avg_water_dist = np.bincount(district_ids, weights=local_water_dist.ravel(), minlength=n) / counts

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

            wx, wz = area.index_to_world(int(x_min[idx]), int(z_min[idx]))
            cx, cz = area.index_to_world(int(x_sum[idx]), int(z_sum[idx]))
            width  = int(x_max[idx]) - int(x_min[idx]) + 1
            depth  = int(z_max[idx]) - int(z_min[idx]) + 1

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

    # ------------------------------------------------------------------

    def _assign_type(
        self,
        slope: float,
        roughness: float,
        water_dist: float,
    ) -> str:
        """
        Assign a district type using the learned MDP policy.

        Bin thresholds are derived once from SettlementConfig in __init__
        via thresholds_from_config() and cached in self._thresholds.

        This means the MDP state space is anchored to the same slope_max,
        roughness_max, and water_dist_max values that govern plot placement
        and road generation — no separate magic numbers to maintain.

        Previously this method used a hand-tuned rule cascade with a random
        tiebreak. The MDP policy is deterministic, principled, and fully
        inspectable via self._mdp.policy_table().
        """
        return self._mdp.act(slope, roughness, water_dist, **self._thresholds)