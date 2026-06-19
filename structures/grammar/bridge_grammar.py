"""
Bridge Grammar Library: Modular Edition
Uses standardized Pillar and Belfry-Face components.
"""
from __future__ import annotations
from gdpc import Block
from structures.base.build_context import BuildContext
from palette.palette_system import palette_get
from structures.orchestrators.primitives.floor import build_floor
from structures.orchestrators.primitives.wall import build_wall
from structures.grammar.wall_grammar import rule_pillar
from structures.orchestrators.primitives.ceiling import build_ceiling
from structures.orchestrators.primitives.roof import build_roof
from structures.grammar.belfry_grammar import _build_belfry_face, rule_belfry

def rule_stone_arch_bridge(ctx: BuildContext, x, y, z, length, width, span_axis="x"):
    """
    Crossing Bridge: Built like a fortification wall.
    Modular: Uses rule_belfry for arches and standard material banding.
    """
    is_x = span_axis == "x"
    wall_mat = palette_get(ctx.palette, "wall", "minecraft:stone_bricks")
    plank_mat = palette_get(ctx.palette, "floor", "minecraft:dark_oak_planks")
    
    n_arches = max(1, length // 6) # Matches fortification spacing
    for i in range(n_arches):
        ax = x + (i * 6) if is_x else x
        az = z if is_x else z + (i * 6)
        bw, bd = (5, width) if is_x else (width, 5)
        
        # Modular: Reuse belfry logic for infrastructure arches
        rule_belfry(ctx, ax, y - 5, az, bw, bd, h=4, style="arched")
        
        # Fill logic matching fortification standards
        for step in range(6):
            for w_off in range(width):
                fx = ax + step if is_x else ax + w_off
                fz = az + w_off if is_x else az + step
                ctx.place_block((fx, y - 1, fz), Block(wall_mat))
                ctx.place_block((fx, y, fz), Block(plank_mat))

    build_wall(ctx, x, y, z, length, 1, width, structure_role="bridge")

def rule_connector_wing_bridge(ctx: BuildContext, x, y, z, length, width, span_axis="x"):
    """
    Tavern Connector: Features fenced walls and deep supporting pillars.
    Modular: Uses rule_pillar and _build_belfry_face.
    """
    plank_mat = palette_get(ctx.palette, "wall", "minecraft:dark_oak_planks")
    stair_mat = palette_get(ctx.palette, "roof", "minecraft:dark_oak_stairs")
    log_mat   = palette_get(ctx.palette, "accent", "minecraft:dark_oak_log")
    trap_mat  = palette_get(ctx.palette, "trapdoor", "minecraft:dark_oak_trapdoor")
    
    width = max(width, 5)
    is_x = span_axis == "x"
    roof_y = y + 5
    ground_depth = 8 

    # 1. Modular Deck & Walls
    # Bridge-role floor is plain planks
    build_floor(ctx, x, y, z, length, width, structure_role="bridge")
    # Bridge-role wall uses _design_fenced
    build_wall(ctx, x, y, z, length, 1, width, structure_role="bridge")

    # 2. Modular Pillars (Supporting Roof & Grounding Structure)
    # Places pillars every 4 blocks along the bridge edges
    pillar_indices = {0, length - 1}
    if length > 8:
        pillar_indices.add(length // 2)
    
    for i in sorted(list(pillar_indices)):
        # Ensure we place a pillar at the very end
        for w_offset in [0, width - 1]:
            px = x + i if is_x else x + w_offset
            pz = z + w_offset if is_x else z + i
            # Modular: Use the pillar component from wall_grammar
            rule_pillar(ctx, px, y - ground_depth, pz, h=ground_depth + 5, material=log_mat)

    # 3. Modular End-Arches (Perpendicular to Axis)
    # Built at the start and end of the bridge span
    for end_coord in [0, length - 1]:
        along_coords = []
        for w_off in range(1, width - 1): # Inset to avoid overlapping corner pillars
            ax = x + end_coord if is_x else x + w_off
            az = z + w_off if is_x else z + end_coord
            along_coords.append((ax, az))
            
        # Modular: Use the specific face builder from belfry_grammar
        _build_belfry_face(
            ctx, roof_y - 1, roof_y - 2,
            along=along_coords,
            plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
            stair_left ={"facing": "south" if is_x else "east", "half": "top"},
            stair_right={"facing": "north" if is_x else "west", "half": "top"}
        )

    # 4. Enclosed Ceiling
    build_ceiling(ctx, x, roof_y, z, length, width, structure_role="bridge_ceiling")

    build_roof(ctx, x, y - 1, z, length, 5, width, structure_role="bridge_roof", connector_side=None)