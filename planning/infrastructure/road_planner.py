from utils.astar import find_path
from utils.mst import mst_edges
from utils.walkable_grid import build_walkable_grid
from utils.path_utils import expand_path_to_width
from data.settlement_entities import RoadCell, Districts
from data.configurations import SettlementConfig
from data.analysis_results import WorldAnalysisResult
from typing import Optional

class RoadPlanner:
    """
    Generates main roads connecting district centers using MST + A*.
    """

    def __init__(
            self,
            analysis: WorldAnalysisResult, 
            districts: Districts, 
            config=None
    ):
        self.analysis = analysis
        self.districts = districts
        self.config = config or SettlementConfig()

    def generate(self) -> Optional[list[RoadCell]]:
        """
        Generate roads connecting district centers.
        Returns a list of RoadCell objects representing the road network.
        """

        if not self.districts:
            print("  ⚠ No building districts available.")
            return

        area = self.analysis.best_area
        road_width = self.config.road_width or 3
        districts = self.districts

        #Compute connection points (center of each district)
        connection_points = [
            dist.center
            for dist in districts.district_list
        ]

        #Build MST edges to minimize total road length
        edges = mst_edges(connection_points)

        #Prepare walkable grid and local heightmap
        local_water = self.analysis.water_mask
        walkable = build_walkable_grid(local_water)
        heightmap_local = self.analysis.heightmap_ground

        #Generate A* paths for each MST edge
        road_cells = set()

        for u, v in edges:
            sx, sz = connection_points[u]
            gx, gz = connection_points[v]

            start = area.world_to_index(int(sx), int(sz))
            goal = area.world_to_index(int(gx), int(gz))

            path = find_path(walkable, heightmap_local, start, goal)

            if path:
                for li, lj in path:
                    wx, wz = area.index_to_world(li, lj)
                    road_cells.add((wx, wz))

        # Expand roads to full width
        bounds = (
            area.x_from, area.x_to,
            area.z_from, area.z_to
        )
        blocked_cells = set()

        expand_cells = expand_path_to_width(
            road_cells, 
            road_width, 
            bounds, 
            blocked_cells)

        return [
            RoadCell(wx, wz)
            for wx, wz in expand_cells
        ]