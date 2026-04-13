from __future__ import annotations
from structures.orchestrators.tower import build_tower
from structures.grammar.fortification_grammar import rule_fortification
from structures.base.build_context import BuildContext
from palette.palette_system import PaletteSystem
from data.build_area import BuildArea
from data.settlement_entities import Building
from data.settlement_entities import Plot
import numpy as np

def build_fortification_settlement(
    ctx: BuildContext, 
    palette: PaletteSystem, 
    heightmap: np.ndarray, 
    area: BuildArea, 
    wall_top_y: int,
    tower_width: int = 5,
    buildings: list[Building] | None = None
) -> None:
    """
    Orchestrator: Receives pre-calculated data and manages the layout.
    1. Places 4 Towers offset 1 block outside the build_area corners.
    2. Builds two parallel wall lines with a 1-block gap on all 4 sides.
    """
    
    # 1. Calculate Tower Positions (1 block outside the build area)
    # NW, NE, SW, SE

    print("area.x_from:", area.x_from, "area.z_from:", area.z_from, "area.x_to:", area.x_to, "area.z_to:", area.z_to)

    offset = tower_width // 2
    print(offset)

    if area.depth % 6 != 0:
        area.z_to -= 6 + (area.depth % 6)

    if area.width % 6 != 0:
        area.x_to -= 6 + (area.width % 6)

    corners = [
        (area.x_from - offset, area.z_from - offset), # NW
        (area.x_to - offset,   area.z_from - offset), # NE
        (area.x_from - offset, area.z_to - offset),   # SW
        (area.x_to - offset,   area.z_to - offset)    # SE
    ]
    print(f"Calculated tower corners at: {corners}")
    
    t_boxes = [(cx, cz, cx + tower_width - 1, cz + tower_width - 1) for cx, cz in corners]
    b_boxes = [(b.x - 1, b.z - 1, b.x + b.width, b.z + b.depth) for b in (buildings or [])]

    for cx, cz in corners:
        # Sample ground for the tower base
        gy = _sample_ground_y(cx, cz, area, heightmap)
        
        # Place Tower
        build_tower(ctx, 
                    Plot(x=cx, y=gy, z=cz, width=tower_width, depth=tower_width),
                    (wall_top_y + 2) - gy)

    print("area.x_from:", area.x_from, "area.z_from:", area.z_from, "area.x_to:", area.x_to, "area.z_to:", area.z_to)
    wall_runs = [
        (area.x_from + offset, area.z_from - 1, area.x_to, area.z_from - 1, True), # North wall
        (area.x_from - 1, area.z_from + offset, area.x_from - 1, area.z_to, False), # West wall
        (area.x_from + offset, area.z_to - 1, area.x_to, area.z_to - 1,   True), # South wall
        (area.x_to - 1, area.z_from + offset, area.x_to - 1, area.z_to, False) #East wall
    ]

    print(f"Calculated wall runs: {wall_runs}")

    for sx, sz, ex, ez, horizontal in wall_runs:
        length = abs(ex - sx) if horizontal else abs(ez - sz)
        
        # Parallel Wall 1 (Inner)
        rule_fortification(ctx, sx, wall_top_y, sz, length, heightmap, area, t_boxes, b_boxes, horizontal)
        
        ox, oz = (0, 2) if horizontal else (2, 0)
        rule_fortification(ctx, sx + ox, wall_top_y, sz + oz, length, heightmap, area, t_boxes, b_boxes, horizontal)

        rule_fortification(ctx, sx + (ox//2), wall_top_y, sz + (oz//2), length, heightmap, area, t_boxes, b_boxes, horizontal, fill_walkway=True)

    return ctx.buffer

def _sample_ground_y(wx, wz, area, heightmap):
    local_x = max(0, min(heightmap.shape[0] - 1, wx - area.x_from))
    local_z = max(0, min(heightmap.shape[1] - 1, wz - area.z_from))
    return int(heightmap[local_x, local_z])