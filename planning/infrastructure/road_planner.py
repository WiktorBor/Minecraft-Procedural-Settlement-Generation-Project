from __future__ import annotations

import logging

import numpy as np

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_entities import Districts, RoadCell
from utils.astar import find_path
from utils.mst import mst_edges
from utils.path_utils import expand_path_to_width
from utils.walkable_grid import build_cost_grid, nearest_walkable

logger = logging.getLogger(__name__)


class RoadPlanner:
    """
    Generates main roads connecting district centres using MST + A*.

    Pipeline
    --------
    1. Compute district centre points in world coordinates.
    2. Build a Minimum Spanning Tree over those points.
    3. Run A* along each MST edge on the cost-weighted heightmap.
    4. Expand the centre-line cells to full road width.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        districts: Districts,
        config: SettlementConfig | None = None,
        hub_point: tuple[float, float] | None = None,
    ) -> None:
        self.analysis   = analysis
        self.districts  = districts
        self.config     = config if config is not None else SettlementConfig()
        self.hub_point  = hub_point  # plaza centre — prepended to MST nodes

    def generate(self) -> list[RoadCell]:
        """
        Generate roads connecting district centres.

        Returns
        -------
        list[RoadCell]
            Road cells in world coordinates representing the full road network.
            Returns an empty list if no districts are available or no paths
            could be found.
        """
        if not self.districts.district_list:
            logger.warning(
                "No building districts available — skipping road generation."
            )
            return []

        area       = self.analysis.best_area
        heightmap  = self.analysis.heightmap_ground
        road_width = self.config.road_width

        costs         = build_cost_grid(self.analysis.water_mask)
        passable_mask = costs < np.inf

        # 1. District centre points in world coordinates.
        #    If a plaza hub is provided, prepend it so the MST connects every
        #    district to the plaza first (radial spoke pattern).
        connection_points = [
            (d.center_x, d.center_z)
            for d in self.districts.district_list
        ]
        if self.hub_point is not None:
            connection_points = [self.hub_point] + connection_points

        # 2. MST over district centres
        edges = mst_edges(connection_points)

        # 3. A* path for each MST edge
        centerline: set[tuple[int, int]] = set()

        for u, v in edges:
            (sx, sz), (gx, gz) = connection_points[u], connection_points[v]

            sx = int(np.clip(sx, area.x_from, area.x_to))
            sz = int(np.clip(sz, area.z_from, area.z_to))
            gx = int(np.clip(gx, area.x_from, area.x_to))
            gz = int(np.clip(gz, area.z_from, area.z_to))

            try:
                start = area.world_to_index(sx, sz)
                goal  = area.world_to_index(gx, gz)
            except ValueError:
                logger.warning(
                    "District centre (%s, %s) → (%s, %s) is outside the "
                    "build area — skipping edge.",
                    sx, sz, gx, gz,
                )
                continue

            # Snap start/goal to nearest non-water cell so A* isn't trapped
            # when a district centre sits on a water tile.
            start = nearest_walkable(*start, passable_mask, max_radius=15) or start
            goal  = nearest_walkable(*goal,  passable_mask, max_radius=15) or goal

            path = find_path(
                passable_mask, heightmap, start, goal,
                height_step_max=3,
                height_cost=0.5,
                costs=costs,
            )

            if path is None:
                logger.warning(
                    "No path found between district centres (%s, %s) "
                    "and (%s, %s).",
                    sx, sz, gx, gz,
                )
                continue

            for li, lj in path:
                wx, wz = area.index_to_world(li, lj)
                centerline.add((wx, wz))

        if not centerline:
            logger.warning(
                "No road cells generated — all paths failed or no edges in MST."
            )
            return []

        bounds   = (area.x_from, area.x_to, area.z_from, area.z_to)
        expanded = expand_path_to_width(
            centerline, road_width, bounds, blocked=set(), organic=True
        )

        final_roads = [
            RoadCell(wx, wz, type="bridge" if self._is_water(wx, wz) else "main_road")
            for wx, wz in expanded
        ]

        logger.info(
            "Generated %d road cells (including %d bridges).",
            len(final_roads),
            sum(1 for r in final_roads if r.type == "bridge"),
        )
        return final_roads

    def _is_water(self, wx: int, wz: int) -> bool:
        """Return True if world coordinate (wx, wz) is a water cell."""
        area = self.analysis.best_area
        if not area.contains_xz(wx, wz):
            return False
        lx, lz = area.world_to_index(wx, wz)
        return bool(self.analysis.water_mask[lx, lz])