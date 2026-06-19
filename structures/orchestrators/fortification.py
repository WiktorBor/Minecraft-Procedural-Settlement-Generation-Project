from __future__ import annotations
import numpy as np
from gdpc import Block
from structures.grammar.fortification_grammar import rule_fortification
from structures.base.build_context import BuildContext
from palette.palette_system import PaletteSystem
from data.build_area import BuildArea
from data.settlement_entities import Building, Plot
from structures.orchestrators.tower import build_tower
from structures.base.geometry import fill_line

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
    Orchestrator for the outer defensive perimeter.
    Creates a double-wall system with a wooden walkway between them.
    """
    push_offset = 4 
    floor_block = Block(ctx.palette.get("floor", "minecraft:spruce_planks"))

    # 1. Preparation for Clipping
    b_boxes = []
    if buildings:
        for b in buildings:
            b_boxes.append((b.x - 1, b.z - 1, b.x + b.width, b.z + b.depth))

    # 2. Corner Tower Placement
    corners = [
        (area.x_from - push_offset - tower_width, area.z_from - push_offset - tower_width), # NW
        (area.x_to + push_offset + 1, area.z_from - push_offset - tower_width),             # NE
        (area.x_from - push_offset - tower_width, area.z_to + push_offset + 1),             # SW
        (area.x_to + push_offset + 1, area.z_to + push_offset + 1)                          # SE
    ]
    
    t_boxes = []
    for cx, cz in corners:
        li = max(0, min(heightmap.shape[0] - 1, cx + (tower_width//2) - area.x_from))
        lj = max(0, min(heightmap.shape[1] - 1, cz + (tower_width//2) - area.z_from))
        gy = int(heightmap[li, lj])
        
        tower_plot = Plot(x=cx, y=gy, z=cz, width=tower_width, depth=tower_width)
        build_tower(ctx, tower_plot, wall_top_y - gy, structure_role="fortification")
        t_boxes.append((cx, cz, cx + tower_width - 1, cz + tower_width - 1))

    # 3. Double Wall Generation with Walkway Fill
    # Defining the four sides of the settlement
    wall_sides = [
        # (Start X, Start Z, Length, Is Horizontal, Offset direction for second wall)
        (area.x_from - push_offset, area.z_from - push_offset, (area.x_to - area.x_from) + (push_offset * 2), True, (0, -tower_width + 1)),   # North
        (area.x_from - push_offset, area.z_to + push_offset, (area.x_to - area.x_from) + (push_offset * 2), True, (0, tower_width - 1)),     # South
        (area.x_from - push_offset, area.z_from - push_offset, (area.z_to - area.z_from) + (push_offset * 2), False, (-tower_width + 1, 0)), # West
        (area.x_to + push_offset, area.z_from - push_offset, (area.z_to - area.z_from) + (push_offset * 2), False, (tower_width - 1, 0))     # East
    ]

    for sx, sz, length, horizontal, offset in wall_sides:
        clear_fortification_path(ctx, sx, sz, length, horizontal, offset, wall_top_y, heightmap, area)

    for sx, sz, length, horizontal, offset in wall_sides:
        dx, dz = offset
        
        # 3a. Build Inner Wall Run
        rule_fortification(ctx, sx, wall_top_y, sz, length, heightmap, area, t_boxes, b_boxes, horizontal)
        
        # 3b. Build Outer Wall Run
        rule_fortification(ctx, sx + dx, wall_top_y, sz + dz, length, heightmap, area, t_boxes, b_boxes, horizontal)
        
        # 3c. Fill Walkway between the two walls
        # Use fill_line for efficiency. We shrink the bounds by 1 to stay BETWEEN walls.
        if horizontal:
            fill_line(
                ctx.buffer,
                sx, wall_top_y - 1, sz + (1 if dz > 0 else -1),
                sx + length, wall_top_y - 1, sz + dz + (-1 if dz > 0 else 1),
                floor_block
            )
        else:
            fill_line(
                ctx.buffer,
                sx + (1 if dx > 0 else -1), wall_top_y - 1, sz,
                sx + dx, wall_top_y - 1, sz + length,
                floor_block
            )
    
    return ctx.buffer

def clear_fortification_path(ctx, sx, sz, length, horizontal, offset, wall_top_y, heightmap, area):
    """
    Clears ONLY the rectangular footprint of the fortification segment.
    """
    air = Block("minecraft:air")
    # We clear a few blocks higher than the wall to remove overhanging branches
    clearance_height = 5 
    
    for i in range(length):
        curr_x = sx + (i if horizontal else 0)
        curr_z = sz + (0 if horizontal else i)
        
        # 1. Get ground height for this specific column
        li = max(0, min(heightmap.shape[0] - 1, curr_x - area.x_from))
        lj = max(0, min(heightmap.shape[1] - 1, curr_z - area.z_from))
        gy = int(heightmap[li, lj])

        # 2. Clear ONLY the tower_width footprint
        # range(0, tower_width) ensures we don't bleed into the settlement
        start, end = offset
        for i in range(start, end):
            for y in range(gy, wall_top_y + clearance_height):
                if horizontal:
                    # Clearing along the Z-axis thickness
                    ctx.place_block((curr_x, y, sz + i), air)
                else:
                    # Clearing along the X-axis thickness
                    ctx.place_block((sx + i, y, curr_z), air)