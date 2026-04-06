from __future__ import annotations

import logging
import math
import random

import numpy as np

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_entities import Plot
from data.settlement_state import OccupancyMap
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
        occupancy: OccupancyMap,
        config: SettlementConfig,
        road_coords: set[tuple[int, int]] | None = None,
    ) -> None:
        self.analysis    = analysis
        self.districts   = districts
        self.config      = config
        self.road_coords = road_coords or set()
        self.occupancy   = occupancy

    # ------------------------------------------------------------------
    # Orientation helpers
    # ------------------------------------------------------------------

    def _facing_toward_road(self, wx: int, wz: int, width: int, depth: int) -> str:
        """
        Return the cardinal direction ("north"/"south"/"east"/"west") of the
        plot edge that is closest to any road cell.

        The nearest road cell is found first; then the direction from the plot
        centre to that cell determines which edge is the "front".
        If no road cells are known, defaults to "south".
        """
        if not self.road_coords:
            return "south"

        cx = wx + width  / 2.0
        cz = wz + depth  / 2.0

        rx, rz = min(
            self.road_coords,
            key=lambda r: (r[0] - cx) ** 2 + (r[1] - cz) ** 2,
        )

        dx = rx - cx
        dz = rz - cz

        if abs(dx) >= abs(dz):
            return "east" if dx >= 0 else "west"
        return "south" if dz >= 0 else "north"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _valid(
        self,
        local_x: int,
        local_z: int,
        plot_w: int,
        plot_d: int,
        dtype: str = "residential",
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
        water_mask = self.analysis.water_mask    [local_x:x_end, local_z:z_end]

        if slope.max() > self.config.max_slope:
            return False
        if roughness.max() > self.config.max_roughness:
            return False

        # Reject any plot where the footprint contains actual water cells.
        if water_mask.any():
            return False

        # Fishing districts may sit close to water; all others need a buffer.
        min_water = (
            self.config.min_water_distance
            if dtype == "fishing"
            else max(self.config.min_water_distance, 3)
        )
        if water_d.min() < min_water:
            return False

        if heights.max() - heights.min() > self.config.max_height_variation:
            return False
        if self.occupancy.blocked(local_x, local_z, plot_w, plot_d):
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

            max_plot_w = self.config.plot_width.get(dtype, 8)
            max_plot_d = self.config.plot_depth.get(dtype, 8)
            min_size   = self.config.min_plot_size.get(dtype, 4)

            area_cap = max(min_size, min(width, depth) // 2)
            max_plot_w = min(max_plot_w, area_cap)
            max_plot_d = min(max_plot_d, area_cap)

            if max_plot_w < min_size or max_plot_d < min_size:
                logger.debug(
                    "District %d (%s): bounding box %dx%d too small for "
                    "min plot size %d, skipping.",
                    district_idx, dtype, width, depth, min_size,
                )
                continue

            for lx, lz in sample_points:
                local_x = int(x_min + lx)
                local_z = int(z_min + lz)

                # Draw a random plot size for this candidate so the settlement
                # gets a natural mix of small and large footprints.
                plot_w = random.randint(min_size, max_plot_w)
                plot_d = random.randint(min_size, max_plot_d)

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
                if not self._valid(local_x, local_z, plot_w, plot_d, dtype):
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

                # Mark padded footprint in the local spacing grid so subsequent
                # plots in this run keep aesthetic distance from each other.
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

                # Register the actual plot footprint in the global occupancy map
                # so later phases (connectors, other planners) see it immediately.
                self.occupancy.add(
                    (wx + dx, wz + dz)
                    for dx in range(plot_w)
                    for dz in range(plot_d)
                )

                # Use the minimum height across the plot footprint as the base Y.
                # level_plot_area will dig higher cells down to this level, so
                # buildings sit at the lowest corner with no dirt fill needed.
                plot_y = int(
                    self.analysis.heightmap_ground[
                        local_x:local_x + plot_w,
                        local_z:local_z + plot_d,
                    ].min()
                )

                facing = self._facing_toward_road(wx, wz, plot_w, plot_d)

                plots.append(Plot(
                    x=wx, z=wz, y=plot_y,
                    width=plot_w, depth=plot_d,
                    type=dtype,
                    facing=facing,
                ))

        logger.info(
            "Generated %d plots across %d districts.",
            len(plots), len(districts_types),
        )
        return plots
