"""
Belfry Grammar
Handles the open-air structural top of towers with a 3-block wide centered arch.
"""
from __future__ import annotations
from typing import Optional
from gdpc import Block
from structures.base.build_context import BuildContext

def rule_belfry(
    ctx: BuildContext, 
    x: int, y: int, z: int, 
    w: int, d: int, 
    h: int = 4, 
    style: str = "arched"
) -> None:
    """
    Main entry point for belfry construction.
    """
    # Material Mapping
    log_mat   = ctx.palette.get("accent", "minecraft:dark_oak_log")
    plank_mat = ctx.palette.get("wall",   "minecraft:dark_oak_planks")
    stair_mat = ctx.palette.get("accent_stair", "minecraft:dark_oak_stairs")
    trap_mat  = ctx.palette.get("trapdoor", "minecraft:dark_oak_trapdoor")

    lintel_y = y + h 
    arch_y   = y + h - 1

    # 1. Corner log columns (full height)
    for dy in range(h):
        for cx, cz in [(x, z), (x + w - 1, z), (x, z + d - 1), (x + w - 1, z + d - 1)]:
            ctx.place_block((cx, y + dy, cz), Block(log_mat))

    # 2. Build the four faces
    # South face (vary X, fixed Z = z)
    _build_belfry_face(ctx, lintel_y, arch_y,
                      along=[(x + dx, z) for dx in range(1, w - 1)],
                      plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                      stair_left ={"facing": "west",  "half": "top"},
                      stair_right={"facing": "east",  "half": "top"})

    # North face (vary X, fixed Z = z + d - 1)
    _build_belfry_face(ctx, lintel_y, arch_y,
                      along=[(x + dx, z + d - 1) for dx in range(1, w - 1)],
                      plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                      stair_left ={"facing": "west",  "half": "top"},
                      stair_right={"facing": "east",  "half": "top"})

    # West face (vary Z, fixed X = x)
    _build_belfry_face(ctx, lintel_y, arch_y,
                      along=[(x, z + dz) for dz in range(1, d - 1)],
                      plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                      stair_left ={"facing": "north", "half": "top"},
                      stair_right={"facing": "south", "half": "top"})

    # East face (vary Z, fixed X = x + w - 1)
    _build_belfry_face(ctx, lintel_y, arch_y,
                      along=[(x + w - 1, z + dz) for dz in range(1, d - 1)],
                      plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                      stair_left ={"facing": "north", "half": "top"},
                      stair_right={"facing": "south", "half": "top"})


def _build_belfry_face(
    ctx: BuildContext,
    lintel_y: int,
    arch_y: int,
    along: list[tuple[int, int]],
    plank_mat: str,
    stair_mat: str,
    trap_mat: str,
    stair_left: dict,
    stair_right: dict,
) -> None:
    """
    Helper to place one arched face: plank lintel row + 3-wide stair arch centered.
    """
    n = len(along)
    if n < 3:
        # If the tower is too skinny, just fill with planks
        for px, pz in along:
            ctx.place_block((px, lintel_y, pz), Block(plank_mat))
        return

    mid      = n // 2
    left_i   = mid - 1
    center_i = mid
    right_i  = mid + 1

    for i, (px, pz) in enumerate(along):
        # Top row is always lintel
        ctx.place_block((px, lintel_y, pz), Block(plank_mat))

        # Determine if we are in the 3-block arch window
        if i == left_i:
            ctx.place_block((px, arch_y, pz), Block(stair_mat, stair_left))
        elif i == center_i:
            # Keystone trapdoor
            ctx.place_block((px, arch_y, pz),
                            Block(trap_mat, {"facing": "south", "open": "false", "half": "top"}))
        elif i == right_i:
            ctx.place_block((px, arch_y, pz), Block(stair_mat, stair_right))
        else:
            # Filler for wider towers
            ctx.place_block((px, arch_y, pz), Block(plank_mat))

        # Ensure the opening below is air (clears out any previous wall/scaffolding)
        for dy in range(1, 3): 
            ctx.place_block((px, arch_y - dy, pz), Block("minecraft:air"))
