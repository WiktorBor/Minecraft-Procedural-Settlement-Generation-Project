from __future__ import annotations

import logging
from utils.astar import find_path
from utils.mst import mst_edges
from utils.walkable_grid import build_walkable_grid
from utils.path_utils import expand_path_to_width
from data.settlement_entities import RoadCell, Districts
from data.configurations import SettlementConfig
from data.analysis_results import WorldAnalysisResult

logger = logging.getLogger(__name__)


class RoadPlanner:
    """
    Generates main roads connecting district centres using MST + A*.

    Pipeline
    --------
    1. Compute district centre points.
    2. Build a Minimum Spanning Tree over those points.
    3. Run A* along each MST edge on the walkable heightmap.
    4. Expand the centre-line cells to full road width.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        districts: Districts,
        config: SettlementConfig | None = None,
    ) -> None:
        self.analysis  = analysis
        self.districts = districts
        self.config    = config if config is not None else SettlementConfig()

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
            logger.warning("No building districts available — skipping road generation.")
            return []

        area       = self.analysis.best_area
        road_width = self.config.road_width
        walkable   = build_walkable_grid(self.analysis.water_mask)
        heightmap  = self.analysis.heightmap_ground

        # 1. District centre points in world coordinates
        connection_points = [
            (d.center_x, d.center_z)
            for d in self.districts.district_list
        ]

        # 2. MST over district centres
        edges = mst_edges(connection_points)

        # 3. A* path for each MST edge
        road_cells: set[tuple[int, int]] = set()

        for u, v in edges:
            sx, sz = connection_points[u]
            gx, gz = connection_points[v]

            try:
                start = area.world_to_index(int(sx), int(sz))
                goal  = area.world_to_index(int(gx), int(gz))
            except ValueError:
                logger.warning(
                    "District centre (%s, %s) → (%s, %s) is outside the build area — skipping edge.",
                    sx, sz, gx, gz,
                )
                continue

            path = find_path(walkable, heightmap, start, goal)

            if path is None:
                logger.warning(
                    "No path found between district centres (%s, %s) and (%s, %s).",
                    sx, sz, gx, gz,
                )
                continue

            for li, lj in path:
                wx, wz = area.index_to_world(li, lj)
                road_cells.add((wx, wz))

        if not road_cells:
            logger.warning("No road cells generated — all paths failed or no edges in MST.")
            return []

        # 4. Expand centre-line to full road width
        bounds = (area.x_from, area.x_to, area.z_from, area.z_to)
        expanded = expand_path_to_width(road_cells, road_width, bounds, blocked=set())

        return [RoadCell(wx, wz) for wx, wz in expanded]