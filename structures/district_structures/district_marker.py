from __future__ import annotations
import logging
import random
import numpy as np

from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Districts, Plot
from structures.base.build_context import BuildContext
from structures.grammar.decoration_grammar import rule_fountain, rule_well
from gdpc import Block # Ensure Block is imported for safety

logger = logging.getLogger(__name__)

_DOCK_W = 14
_DOCK_D = 10

class DistrictMarker:
    def __init__(self, analysis: WorldAnalysisResult, ctx: BuildContext) -> None:
        self.analysis = analysis
        self.ctx = ctx

    def build(self, districts: Districts, occupancy: set[tuple[int, int]]) -> list[tuple[int, int]]:
        taken: set[tuple[int, int]] = set()
        area = self.analysis.best_area
        water = self.analysis.water_mask.astype(bool)

        for idx, district in enumerate(districts.district_list):
            dtype = districts.types.get(idx, "")
            
            # REFACTOR: Find the best placement based on type
            if dtype == "fishing":
                # Find a spot near water instead of the center
                pos = self._find_waterfront_spot(district, area, water, occupancy)
                if pos:
                    cx, cz = pos
                    li, lj = area.world_to_index(cx, cz)
                    cy = int(self.analysis.heightmap_ground[li, lj])
                    self._place_dock(cx, cy, cz, area, water, taken)
                    logger.info("Dock placed at waterfront for district %d at (%d, %d).", idx, cx, cz)
                continue

            # Standard center-based placement for other markers
            cx, cz = int(district.center_x), int(district.center_z)
            if (cx, cz) in occupancy or not area.contains_xz(cx, cz):
                continue

            li, lj = area.world_to_index(cx, cz)
            cy = int(self.analysis.heightmap_ground[li, lj])

            choice = random.choice(["fountain", "well"])
            if choice == "well":
                rule_well(self.ctx, cx - 1, cy, cz - 1)
                self._mark_taken(cx, cz, 3, taken)
            else:
                rule_fountain(self.ctx, cx, cy, cz)
                self._mark_taken(cx, cz, 5, taken)
            
        return list(taken)

    def _find_waterfront_spot(self, district, area, water, occupancy):
        """Searches district cells to find one that is ground but touches water."""
        best_pos = None
        min_dist_to_center = float('inf')
        
        # Spiral outward from center to find the closest waterfront
        search_radius = 15 
        cx, cz = int(district.center_x), int(district.center_z)
        
        for dx in range(-search_radius, search_radius + 1):
            for dz in range(-search_radius, search_radius + 1):
                wx, wz = cx + dx, cz + dz
                
                if not area.contains_xz(wx, wz) or (wx, wz) in occupancy:
                    continue
                
                li, lj = area.world_to_index(wx, wz)
                
                # Check if this cell is GROUND but has WATER adjacent
                if not water[li, lj]: # It's land
                    # Look at 4 neighbors for water
                    has_water_neighbor = False
                    for ni, nj in [(li-1, lj), (li+1, lj), (li, lj-1), (li, lj+1)]:
                        if 0 <= ni < water.shape[0] and 0 <= nj < water.shape[1]:
                            if water[ni, nj]:
                                has_water_neighbor = True
                                break
                    
                    if has_water_neighbor:
                        dist = dx*dx + dz*dz
                        if dist < min_dist_to_center:
                            min_dist_to_center = dist
                            best_pos = (wx, wz)
        
        return best_pos if best_pos else (cx, cz)

    def _place_dock(self, cx: int, cy: int, cz: int, area, water, taken: set) -> None:
        from structures.orchestrators.dock import build_dock
        from structures.buffer_transform import rotate_buffer

        # Clamp dock origin so it stays inside the build area
        wx = max(area.x_from, min(area.x_to - _DOCK_W + 1, cx - _DOCK_W // 2))
        wz = max(area.z_from, min(area.z_to - _DOCK_D + 1, cz - _DOCK_D // 2))

        plot = Plot(x=wx, z=wz, y=cy, width=_DOCK_W, depth=_DOCK_D, type="fishing")

        try:
            from world_interface.block_buffer import BlockBuffer
            dock_buf = BlockBuffer()
            dock_ctx = BuildContext(buffer=dock_buf, palette=self.ctx.palette)
            build_dock(dock_ctx, plot)

            rotation = self._water_facing_rotation(cx, cz, area, water)
            if rotation != 0:
                dock_buf = rotate_buffer(dock_buf, wx, wz, _DOCK_W, _DOCK_D, rotation)

            self.ctx.buffer.merge(dock_buf)
        except Exception:
            logger.error("Dock marker build failed at (%d, %d).", wx, wz, exc_info=True)
            return

        for dx in range(-2, _DOCK_W + 2):
            for dz in range(-2, _DOCK_D + 2):
                taken.add((wx + dx, wz + dz))

    @staticmethod
    def _water_facing_rotation(cx: int, cz: int, area, water) -> int:
        """Return the clockwise rotation that orients the pier toward the most water."""
        radius = max(_DOCK_W, _DOCK_D)
        counts = {"north": 0, "south": 0, "east": 0, "west": 0}
        for d in range(1, radius + 1):
            for wx, wz, direction in [
                (cx,     cz - d, "north"),
                (cx,     cz + d, "south"),
                (cx + d, cz,     "east"),
                (cx - d, cz,     "west"),
            ]:
                if not area.contains_xz(wx, wz):
                    continue
                li, lj = area.world_to_index(wx, wz)
                if water[li, lj]:
                    counts[direction] += 1

        best = max(counts, key=counts.get)
        # Dock pier faces south by default; rotate to face the water
        return {"south": 0, "west": 90, "north": 180, "east": 270}[best]

    def _mark_taken(self, cx: int, cz: int, size: int, taken: set) -> None:
        offset = size // 2
        for dx in range(-offset, offset + 1):
            for dz in range(-offset, offset + 1):
                taken.add((cx + dx, cz + dz))
