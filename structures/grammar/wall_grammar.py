"""
Wall Grammar Design Library
Focus: Geometric patterns, material distribution, and structural components.
"""
from __future__ import annotations
from gdpc import Block
from structures.base.build_context import BuildContext

# --- DISPATCHER ---
def rule_wall(ctx: BuildContext, x, y, z, w, h, d, style="plain", skip_sides=None):
    """Main entry point for building 4-sided wall enclosures."""
    # Standardize Palette Mapping
    mat_wall = ctx.palette.get("wall")
    mat_acc  = ctx.palette.get("accent")
    mat_base = ctx.palette.get("foundation")
    mat_fence = ctx.palette.get("fence")

    if style == "fenced":
        _design_fenced(ctx, x, y, z, w, h, d, mat_fence, skip_sides)
    elif style == "tower":
        # Tower style: Heavy corners with banded curtain walls
        _design_stone_tower_walls(ctx, x, y, z, w, h, d, mat_wall, mat_base, skip_sides)
    elif style == "timber":
        _design_timber(ctx, x, y, z, w, h, d, mat_wall, mat_acc, skip_sides)
    else:
        _design_plain(ctx, x, y, z, w, h, d, mat_wall, skip_sides)

# --- COMPONENT: PILLARS ---
def rule_pillar(ctx, x, y, z, h, material=None):
    """Builds a single vertical column. Used for corners."""
    mat = material if material else ctx.palette.get("wall")
    for dy in range(h):
        ctx.place_block((x, y + dy, z), Block(mat))

# --- DESIGN: STONE TOWER (Modular Components) ---
def _design_stone_tower_walls(ctx, x, y, z, w, h, d, mat_wall, mat_base, skip_sides):
    """
    Builds thick corners (pillars) and fills the gaps with banded walls.
    """
    # 1. Build the 4 Corners using the Pillar rule
    corners = [(x, z), (x + w - 1, z), (x, z + d - 1), (x + w - 1, z + d - 1)]
    for cx, cz in corners:
        rule_pillar(ctx, cx, y, cz, h, material=mat_base) # Towers often use base mat for corners

    # 2. Fill the spans (Curtain Walls)
    # Note: We loop from 1 to w-2 to avoid overwriting the pillars
    split_dy = 2
    for dy in range(h):
        curr_y = y + dy
        curr_mat = mat_base if dy <= split_dy else mat_wall
        
        # North/South spans
        if "north" not in skip_sides:
            for dx in range(1, w - 1):
                ctx.place_block((x + dx, curr_y, z), Block(curr_mat))
        if "south" not in skip_sides:
            for dx in range(1, w - 1):
                ctx.place_block((x + dx, curr_y, z + d - 1), Block(curr_mat))
                
        # East/West spans
        if "west" not in skip_sides:
             for dz in range(1, d - 1):
                ctx.place_block((x, curr_y, z + dz), Block(curr_mat))
        if "east" not in skip_sides:
            for dz in range(1, d - 1):
                ctx.place_block((x + w - 1, curr_y, z + dz), Block(curr_mat))

# --- DESIGN: TIMBER (Tudor framework) ---
def _design_timber(ctx, x, y, z, w, h, d, mat_fill, mat_frame, skip_sides):
    beam_dy = h // 2 + 1 
    for dy in range(h):
        wy = y + dy
        is_frame_h = (dy == 0 or dy == h - 1 or dy == beam_dy)

        for dx in range(w):
            for fz in (z, z + d - 1):
                is_corner = (dx == 0 or dx == w - 1)
                if is_corner or is_frame_h:
                    ctx.place_block((x + dx, wy, fz), Block(mat_frame))
                else:
                    ctx.place_block((x + dx, wy, fz), Block(mat_fill))

        for dz in range(1, d - 1):
            for fx in (x, x + w - 1):
                if is_frame_h:
                    ctx.place_block((fx, wy, z + dz), Block(mat_frame))
                else:
                    ctx.place_block((fx, wy, z + dz), Block(mat_fill))

# --- DESIGN: PLAIN (Solid shell) ---
def _design_plain(ctx, x, y, z, w, h, d, material,skip_sides):
    for dy in range(h):
        wy = y + dy
        if "north" not in skip_sides:
            for dx in range(w):
                ctx.place_block((x + dx, wy, z), Block(material))

        if "south" not in skip_sides:
            for dx in range(w):
                ctx.place_block((x + dx, wy, z + d - 1), Block(material))

        if "west" not in skip_sides:
            for dz in range(1, d - 1):
                ctx.place_block((x, wy, z + dz), Block(material))
        
        if "east" not in skip_sides:
            for dz in range(1, d - 1):
                ctx.place_block((x + w - 1, wy, z + dz), Block(material))

def _design_fenced(ctx, x, y, z, w, h, d, material, skip_sides):
    for dy in range(1, h + 1):
        wy = y + dy
        if w >= d:
            for dx in range(w):
                ctx.place_block((x + dx, wy, z), Block(material))
                ctx.place_block((x + dx, wy, z + d - 1), Block(material))
        else:
            for dz in range(d):
                ctx.place_block((x, wy, z + dz), Block(material))
                ctx.place_block((x + w - 1, wy, z + dz), Block(material))