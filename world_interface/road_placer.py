from collections.abc import Iterable

from gdpc import Block
from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import RoadCell
from data.biome_palettes import BiomePalette


class RoadBuilder:
    """
    Places road blocks in the world from a collection of RoadCell coordinates.

    The road block is taken from the biome palette's 'path' entry so that
    desert settlements get sand paths, taiga settlements get gravel, etc.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette,
    ) -> None:
        self.editor   = editor
        self.analysis = analysis
        self._block   = Block(palette["path"])

    def build(self, roads: Iterable[RoadCell]) -> None:
        """
        Place road blocks at each RoadCell position.

        Each block is placed one level below the ground heightmap so that
        roads sit flush with the terrain surface.

        Args:
            roads: Any iterable of RoadCell objects (list, set, generator).

        Note
        ----
        Wrap this call in editor.pushBuffer() / editor.popBuffer() to batch
        all placements into a single HTTP request.
        """
        heightmap = self.analysis.heightmap_ground
        area      = self.analysis.best_area

        for cell in roads:
            try:
                li, lj = area.world_to_index(cell.x, cell.z)
            except ValueError:
                continue  # cell is outside the build area — skip silently

            y = int(heightmap[li, lj]) - 1
            self.editor.placeBlock((cell.x, y, cell.z), self._block)