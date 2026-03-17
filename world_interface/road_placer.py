from gdpc import Block
from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import RoadCell
from typing import List, Any

class RoadBuilder:
    """
    Places roads in the world based on RoadCell coordinates.
    """

    def __init__(self, editor: Any, analysis: WorldAnalysisResult):
        self.editor = editor
        self.analysis = analysis

    def build(self, roads: List[RoadCell]) -> None:
        """
        Build roads at the given RoadCell positions.
        
        Parameters
        ----------
        roads : List[RoadCell]
            A list of RoadCell objects containing world coordinates for road placement.
        """

        heightmap = self.analysis.heightmap_ground
        base_x, base_z = self.analysis.best_area.x_from, self.analysis.best_area.z_from

        for cell in roads:
            wx, wz = cell.x, cell.z

            li = wx - base_x
            lj = wz - base_z

            if not (0 <= li < heightmap.shape[0] and 0 <= lj < heightmap.shape[1]):
                continue

            y = int(heightmap[li, lj]) - 1
            self.editor.placeBlock((wx, y, wz), Block("minecraft:gravel"))