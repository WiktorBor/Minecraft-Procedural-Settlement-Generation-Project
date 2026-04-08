"""
Dynamic village-style road placement.

Main roads get a 3-block-wide core with organic edge blocks that taper off.
Connector paths are narrow 1-block footpaths.  Both adapt to height
transitions with slabs and use varied materials from the biome palette.
"""
from __future__ import annotations

import logging
import random
from collections.abc import Iterable

from gdpc import Block

from data.analysis_results import WorldAnalysisResult
from palette.palette_system import PaletteSystem, palette_get
from data.settlement_entities import RoadCell
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)

_NEIGHBOURS_4 = [(0, 1), (0, -1), (1, 0), (-1, 0)]


class RoadBuilder:
    """
    Places road blocks with per-cell material variation so paths look
    hand-built rather than machine-stamped.

    Material logic
    --------------
    * **Interior** cells (surrounded by other road cells) get the main
      ``path`` block.
    * **Edge** cells (fewer road neighbours) get ``path_edge`` with a
      random chance of the main block bleeding through.
    * **Connector** cells always use ``path`` at width 1.
    * When a cell is 1 block higher than a road neighbour, a ``path_slab``
      is placed instead to create a smooth step.
    * Occasional random lanterns are placed on edge cells for atmosphere.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        palette: PaletteSystem,
    ) -> None:
        self.analysis  = analysis
        self._path     = Block(palette["path"])
        self._edge     = Block(palette_get(palette, "path_edge", palette["path"]))
        self._slab     = Block(palette_get(palette, "path_slab", palette["path"]),
                               {"type": "bottom"})
        self._light    = Block(palette_get(palette, "light", "minecraft:lantern"))
        self._fence    = Block(palette_get(palette, "fence", "minecraft:oak_fence"))

    def build(self, roads: Iterable[RoadCell]) -> BlockBuffer:
        """
        Build road blocks into a BlockBuffer.

        Cells are classified by their neighbourhood density to decide
        block material.  Height transitions between adjacent road cells
        produce slab half-steps.
        """
        heightmap = self.analysis.heightmap_ground
        area      = self.analysis.best_area
        buffer    = BlockBuffer()

        cells: list[RoadCell] = list(roads)
        if not cells:
            return buffer

        # Build a lookup so we can inspect each cell's neighbours in O(1).
        coord_set: set[tuple[int, int]] = {(c.x, c.z) for c in cells}

        rng = random.Random(42)

        light_counter = 0

        for cell in cells:
            try:
                li, lj = area.world_to_index(cell.x, cell.z)
            except ValueError:
                continue

            y = int(heightmap[li, lj]) - 1

            is_connector = cell.type == "connector"

            # Count how many 4-connected road neighbours this cell has.
            road_neighbours = 0
            min_neighbour_y = y
            max_neighbour_y = y
            for dx, dz in _NEIGHBOURS_4:
                nx, nz = cell.x + dx, cell.z + dz
                if (nx, nz) in coord_set:
                    road_neighbours += 1
                    try:
                        ni, nj = area.world_to_index(nx, nz)
                        ny = int(heightmap[ni, nj]) - 1
                        min_neighbour_y = min(min_neighbour_y, ny)
                        max_neighbour_y = max(max_neighbour_y, ny)
                    except ValueError:
                        pass

            # Height transition: when this cell is higher than a neighbour,
            # place a slab for a smooth half-step.
            if y > min_neighbour_y and (y - min_neighbour_y) == 1:
                buffer.place(cell.x, y, cell.z, self._slab)
                continue

            # Pick material based on neighbourhood density.
            if is_connector:
                block = self._path
                # Connectors occasionally get edge material for variety
                if rng.random() < 0.15:
                    block = self._edge
            elif road_neighbours >= 3:
                # Interior cell — main path with rare edge variation
                block = self._path
                if rng.random() < 0.08:
                    block = self._edge
            else:
                # Edge or tip cell
                block = self._edge
                if rng.random() < 0.3:
                    block = self._path

            buffer.place(cell.x, y, cell.z, block)

            # Occasional lanterns on edge cells of main roads (not connectors)
            if (not is_connector
                    and road_neighbours <= 2
                    and rng.random() < 0.06):
                light_counter += 1
                buffer.place(cell.x, y + 1, cell.z, self._fence)
                buffer.place(cell.x, y + 2, cell.z, self._light)

        logger.info(
            "RoadBuilder: built %d cells (%d with lanterns).",
            len(cells), light_counter,
        )
        return buffer
