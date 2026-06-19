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
import numpy as np

from gdpc import Block

from data.analysis_results import WorldAnalysisResult
from palette.palette_system import PaletteSystem, palette_get
from data.settlement_entities import RoadCell
from world_interface.block_buffer import BlockBuffer
from structures.orchestrators.primitives.bridge import build_bridge
from structures.base.build_context import BuildContext
from data.settlement_entities import Plot


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
        self.palette   = palette
        self._path     = Block(palette["path"])
        self._edge     = Block(palette_get(palette, "path_edge", palette["path"]))
        self._slab     = Block(palette_get(palette, "path_slab", palette["path"]),
                               {"type": "bottom"})
        self._light    = Block(palette_get(palette, "light", "minecraft:lantern"))
        self._fence    = Block(palette_get(palette, "fence", "minecraft:oak_fence"))

    def build(self, roads: Iterable[RoadCell]) -> BlockBuffer:
        """
        Build road and bridge blocks into a BlockBuffer.
        Groups contiguous bridge cells to build them as single orchestrator units.
        """
        heightmap = self.analysis.heightmap_ground
        area      = self.analysis.best_area
        buffer    = BlockBuffer()
        all_cells = list(roads)
        
        if not all_cells:
            return buffer

        # 1. Separate bridge cells from standard road cells
        bridge_cells = [c for c in all_cells if c.type == "bridge"]
        standard_cells = [c for c in all_cells if c.type != "bridge"]
        
        # 2. Process Bridge Chunks via Orchestrator
        if bridge_cells:
            # Group individual bridge cells into connected segments
            segments = self._group_bridge_segments(bridge_cells)
            
            for segment in segments:
                # Calculate the bounding box for the entire bridge span
                min_x = min(c.x for c in segment)
                max_x = max(c.x for c in segment)
                min_z = min(c.z for c in segment)
                max_z = max(c.z for c in segment)
                
                width = (max_x - min_x) + 1
                depth = (max_z - min_z) + 1
                
                # Determine if the bridge is mainly East-West or North-South
                axis = "x" if width >= depth else "z"
                
                water_indices = np.where(self.analysis.water_mask)
                if len(water_indices[0]) > 0:
                    # Use the median or max height of the area where water exists
                    sea_level = int(np.median(heightmap[water_indices]))

                else:
                    # Fallback if no water is detected; use a default sea level
                    sea_level = 62
                    
                # Create a Plot object representing the bridge footprint
                # bridge_y is set to 1 block above sea level
                bridge_plot = Plot(
                    x=min_x, z=min_z, 
                    y=sea_level + 1,
                    width=width, depth=depth
                )
                
                # Use a local context to capture the orchestrator's output
                temp_buf = BlockBuffer()
                ctx = BuildContext(buffer=temp_buf, palette=self.palette)
                
                # Call the infrastructure bridge orchestrator
                build_bridge(ctx, bridge_plot, structure_role="infrastructure", span_axis=axis)
                buffer.merge(temp_buf)

        # 3. Process Standard Road Cells (existing logic)
        coord_set: set[tuple[int, int]] = {(c.x, c.z) for c in all_cells}
        rng = random.Random(42)

        for cell in standard_cells:
            try:
                li, lj = area.world_to_index(cell.x, cell.z)
            except ValueError:
                continue

            y = int(heightmap[li, lj]) - 1
            is_connector = cell.type == "connector"

            # Determine material density based on neighbors
            road_neighbours = sum(1 for dx, dz in _NEIGHBOURS_4 if (cell.x + dx, cell.z + dz) in coord_set)
            
            # Height transition slab logic
            min_ny = y
            for dx, dz in _NEIGHBOURS_4:
                nx, nz = cell.x + dx, cell.z + dz
                if (nx, nz) in coord_set:
                    try:
                        ni, nj = area.world_to_index(nx, nz)
                        min_ny = min(min_ny, int(heightmap[ni, nj]) - 1)
                    except ValueError: pass

            if y > min_ny and (y - min_ny) == 1:
                buffer.place(cell.x, y, cell.z, self._slab)
                continue

            # Pick material
            if is_connector:
                block = self._path
                if rng.random() < 0.15: block = self._edge
            elif road_neighbours >= 3:
                block = self._path
            else:
                block = self._edge

            buffer.place(cell.x, y, cell.z, block)

            # Stochastically place fence post + lantern on edge cells
            if not is_connector and road_neighbours <= 1 and rng.random() < 0.18:
                buffer.place(cell.x, y + 1, cell.z, self._fence)
                buffer.place(cell.x, y + 2, cell.z, self._light)

        return buffer

    def _group_bridge_segments(self, bridge_cells: list[RoadCell]) -> list[list[RoadCell]]:
        """
        Uses Breadth-First Search to group adjacent bridge cells into contiguous segments.
        """
        unvisited = set((c.x, c.z) for c in bridge_cells)
        cell_map = {(c.x, c.z): c for c in bridge_cells}
        segments = []

        while unvisited:
            curr_coord = unvisited.pop()
            segment = [cell_map[curr_coord]]
            queue = [curr_coord]
            
            while queue:
                x, z = queue.pop(0)
                for dx, dz in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    neighbor = (x + dx, z + dz)
                    if neighbor in unvisited:
                        unvisited.remove(neighbor)
                        segment.append(cell_map[neighbor])
                        queue.append(neighbor)
            segments.append(segment)
        return segments