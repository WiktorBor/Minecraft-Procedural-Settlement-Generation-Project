from __future__ import annotations

import logging
import math

import numpy as np

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_entities import Plot
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
        districts,
        taken: set[tuple[int, int]],
        config: SettlementConfig,
    ) -> None:
        self.analysis  = analysis
        self.districts = districts
        self.config    = config

        # Pre-build a boolean grid of taken cells in local index space so that
        # overlap checks in _valid() are a single numpy slice rather than an
        # O(plot_w × plot_d) Python loop.
        shape = analysis.heightmap_ground.shape
        self._taken_mask: np.ndarray = np.zeros(shape, dtype=bool)
        _area = analysis.best_area
        for wx, wz in taken:
            try:
                li, lj = _area.world_to_index(wx, wz)
                self._taken_mask[li, lj] = True
            except ValueError:
                pass  # cell outside best_area — ignore

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
        x_end = local_x + plot_w
        z_end = local_z + plot_d

        if x_end > self.analysis.heightmap_ground.shape[0]:
            return False
        if z_end > self.analysis.heightmap_ground.shape[1]:
            return False

        slope     = self.analysis.slope_map      [local_x:x_end, local_z:z_end]
        roughness = self.analysis.roughness_map  [local_x:x_end, local_z:z_end]
        water_d   = self.analysis.water_distances[local_x:x_end, local_z:z_end]
        heights   = self.analysis.heightmap_ground[local_x:x_end, local_z:z_end]

        if slope.max() > self.config.max_slope:
            return False
        if roughness.max() > self.config.max_roughness:
            return False
        if water_d.min() < self.config.min_water_distance:
            return False
        if heights.max() - heights.min() > self.config.max_height_variation:
            return False
        if self._taken_mask[local_x:x_end, local_z:z_end].any():
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
        plots:    list[Plot] = []

        for district_idx, dtype in districts_types.items():
            plot_centers: list[tuple[int, int]] = []
            district_mask = districts_map == district_idx
            if not np.any(district_mask):
                continue

            # Spacing by district type
            min_dist = self.config.min_plot_distance
            if   dtype == "residential": min_dist = max(6, min_dist // 2)
            elif dtype == "farming":     min_dist = int(min_dist * 1.5)
            elif dtype == "forest":      min_dist = int(min_dist * 2)

            xs, zs = np.where(district_mask)
            x_min, x_max = int(xs.min()), int(xs.max())
            z_min, z_max = int(zs.min()), int(zs.max())
            width  = x_max - x_min + 1
            depth  = z_max - z_min + 1

            sample_points = poisson_disk(
                width=width, depth=depth, radius=min_dist
            )

            plot_w   = self.config.plot_width.get(dtype, 8)
            plot_d   = self.config.plot_depth.get(dtype, 8)
            min_size = self.config.min_plot_size.get(dtype, 4)

            max_plot = max(min_size, min(width, depth) // 2)
            plot_w   = min(plot_w, max_plot)
            plot_d   = min(plot_d, max_plot)

            if plot_w < min_size or plot_d < min_size:
                logger.debug(
                    "District %d (%s): bounding box %dx%d too small for "
                    "min plot size %d, skipping.",
                    district_idx, dtype, width, depth, min_size,
                )
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
                if np.any(occ_slice):
                    continue
                if dist_slice.mean() < 0.5:
                    continue
                if not self._valid(local_x, local_z, plot_w, plot_d):
                    continue

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

                # Mark footprint + buffer as occupied.
                # grammar_max accounts for the worst-case dimension the house
                # grammar can snap to, preventing structure overlap in the world.
                grammar_max = 11
                effective_w = max(plot_w, grammar_max)
                effective_d = max(plot_d, grammar_max)
                block_r     = self.config.min_plot_cluster_distance // 2
                occupied[
                    max(0, local_x - block_r):min(w, local_x + effective_w + block_r),
                    max(0, local_z - block_r):min(d, local_z + effective_d + block_r),
                ] = True

                plot_centers.append((cx, cz))

                wx, wz = self.analysis.best_area.index_to_world(local_x, local_z)

                # Use the maximum height across the plot footprint as the base Y.
                # Builders fill downward from this height to meet lower terrain cells.
                plot_y = int(
                    self.analysis.heightmap_ground[
                        local_x:local_x + plot_w,
                        local_z:local_z + plot_d,
                    ].max()
                )

                plots.append(Plot(
                    x=wx, z=wz, y=plot_y,
                    width=plot_w, depth=plot_d,
                    type=dtype,
                ))

        logger.info(
            "Generated %d plots across %d districts.",
            len(plots), len(districts_types),
        )
        return plots