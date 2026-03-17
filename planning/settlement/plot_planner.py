from __future__ import annotations

import math
import logging
from collections.abc import Iterable

import numpy as np

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_entities import District, Districts, Plot, RoadCell
from utils.poisson_disk import poisson_disk

logger = logging.getLogger(__name__)


class PlotPlanner:
    """
    Creates building plots within each Voronoi district, ensuring plots fit
    terrain constraints and do not overlap roads or each other.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        districts: Districts,
        roads: Iterable[RoadCell],
        config: SettlementConfig,
    ) -> None:
        self.analysis  = analysis
        self.districts = districts
        self.roads     = frozenset(roads)   # O(1) membership, immutable
        self.config    = config

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _valid(
        self,
        local_x: int,
        local_z: int,
        plot_w: int,
        plot_d: int,
    ) -> bool:
        """
        Validate a plot rectangle using vectorised array slicing.

        All terrain checks are performed on numpy slices — no Python loop
        over individual cells.
        """
        area  = self.analysis.best_area
        x_end = local_x + plot_w
        z_end = local_z + plot_d

        # Bounds check
        if x_end > self.analysis.heightmap_ground.shape[0]:
            return False
        if z_end > self.analysis.heightmap_ground.shape[1]:
            return False

        slope     = self.analysis.slope_map      [local_x:x_end, local_z:z_end]
        roughness = self.analysis.roughness_map  [local_x:x_end, local_z:z_end]
        water_d   = self.analysis.water_distances[local_x:x_end, local_z:z_end]
        heights   = self.analysis.heightmap_ground[local_x:x_end, local_z:z_end]

        if slope.max() > self.config.max_slope:
            logger.debug("  rejected: slope %.2f > %.2f", float(slope.max()), self.config.max_slope)
            return False
        if roughness.max() > self.config.max_roughness:
            logger.debug("  rejected: roughness %.2f > %.2f", float(roughness.max()), self.config.max_roughness)
            return False
        if water_d.min() < self.config.min_water_distance:
            logger.debug("  rejected: water_dist %.2f < %d", float(water_d.min()), self.config.min_water_distance)
            return False
        if heights.max() - heights.min() > self.config.max_height_variation:
            logger.debug("  rejected: height_var %.2f > %d", float(heights.max() - heights.min()), self.config.max_height_variation)
            return False

        # Road overlap
        wx0, wz0 = area.index_to_world(local_x, local_z)
        for dx in range(plot_w):
            for dz in range(plot_d):
                if RoadCell(wx0 + dx, wz0 + dz) in self.roads:
                    logger.debug("  rejected: road overlap at (%d, %d)", wx0+dx, wz0+dz)
                    return False

        return True

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> list[Plot]:
        """
        Generate plots inside each Voronoi district.

        Returns
        -------
        list[Plot]
            All valid, non-overlapping plots across all districts.
        """
        districts_map   = self.districts.map
        districts_types = self.districts.types

        w, d     = districts_map.shape
        occupied = np.zeros((w, d), dtype=bool)

        plots:        list[Plot]           = []
        plot_centers: list[tuple[int,int]] = []

        for district_idx, dtype in districts_types.items():
            district_mask = districts_map == district_idx
            if not np.any(district_mask):
                continue

            # Spacing by district type
            min_dist = self.config.min_plot_distance
            if   dtype == "residential": min_dist = max(2, min_dist // 2)
            elif dtype == "farming":     min_dist = int(min_dist * 1.5)
            elif dtype == "forest":      min_dist = int(min_dist * 2)

            # Bounding box of this district
            xs, zs = np.where(district_mask)
            x_min, x_max = int(xs.min()), int(xs.max())
            z_min, z_max = int(zs.min()), int(zs.max())
            width  = x_max - x_min + 1
            depth  = z_max - z_min + 1

            sample_points = poisson_disk(width=width, height=depth, radius=min_dist)

            plot_w   = self.config.plot_width.get(dtype, 8)
            plot_d   = self.config.plot_depth.get(dtype, 8)
            min_size = self.config.min_plot_size.get(dtype, 4)

            # Auto-scale plot size down if the district bounding box is too small
            max_plot = max(min_size, min(width, depth) // 2)
            plot_w   = min(plot_w, max_plot)
            plot_d   = min(plot_d, max_plot)

            if plot_w < min_size or plot_d < min_size:
                logger.debug("District %d (%s): bounding box %dx%d too small for min plot size %d, skipping.",
                             district_idx, dtype, width, depth, min_size)
                continue

            for lx, lz in sample_points:
                local_x = int(x_min + lx)
                local_z = int(z_min + lz)

                if local_x + plot_w > w or local_z + plot_d > d:
                    continue

                occ_slice  = occupied     [local_x:local_x + plot_w, local_z:local_z + plot_d]
                dist_slice = district_mask[local_x:local_x + plot_w, local_z:local_z + plot_d]

                if occ_slice.shape != (plot_w, plot_d):
                    continue
                # Reject if any cell is already occupied
                if np.any(occ_slice):
                    continue
                # Require at least 50% of the plot to lie within this district
                if dist_slice.mean() < 0.5:
                    continue

                if not self._valid(local_x, local_z, plot_w, plot_d):
                    continue

                # Cluster distance check
                cx = local_x + plot_w // 2
                cz = local_z + plot_d // 2

                if plot_centers:
                    nearest = min(
                        math.hypot(cx - px, cz - pz)
                        for px, pz in plot_centers
                    )
                    if nearest < self.config.min_plot_cluster_distance:
                        continue
                    if nearest > self.config.max_plot_cluster_distance:
                        if np.random.random() < 0.6:
                            continue

                # Mark footprint + buffer as occupied
                block_r = self.config.min_plot_cluster_distance // 2
                occupied[
                    max(0, local_x - block_r):min(w, local_x + plot_w + block_r),
                    max(0, local_z - block_r):min(d, local_z + plot_d + block_r),
                ] = True

                plot_centers.append((cx, cz))

                wx, wz = self.analysis.best_area.index_to_world(local_x, local_z)
                plots.append(Plot(
                    x=wx,
                    z=wz,
                    y=int(self.analysis.heightmap_ground[local_x, local_z]),
                    width=plot_w,
                    depth=plot_d,
                    type=dtype,
                ))

        logger.info("Generated %d plots across %d districts.", len(plots), len(districts_types))
        return plots