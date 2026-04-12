from __future__ import annotations
from gdpc import Block
from structures.base.build_context import BuildContext
from structures.base.geometry import fill_cuboid, fill_cuboid_wireframe, fill_line

def rule_well(ctx: BuildContext, x: int, y: int, z: int):
    """A 3×3 stone-brick well with a roof."""
    wall_mat  = ctx.palette["wall"]
    acc_mat   = ctx.palette["accent"]
    found_mat = ctx.palette["foundation"]
    light_mat = ctx.palette.get("light", "minecraft:lantern")

    # Foundation (4 deep)
    fill_cuboid(ctx.buffer, x, y - 4, z, x + 2, y - 1, z + 2, Block(found_mat))

    # Base and Water
    fill_cuboid_wireframe(ctx.buffer, x, y, z, x + 2, y, z + 2, Block(wall_mat))
    ctx.place_block((x + 1, y, z + 1), Block("minecraft:water"))

    # Supports
    fill_cuboid_wireframe(ctx.buffer, x, y + 1, z, x + 2, y + 2, z + 2, Block(wall_mat))

    # Roof beams
    for bx, bz in [(x, z), (x+2, z), (x, z+2), (x+2, z+2), (x+1, z), (x+1, z+2)]:
        ctx.place_block((bx, y + 3, bz), Block(acc_mat))

    # Hanging Lantern
    ctx.place_block((x + 1, y + 3, z + 1), Block(light_mat, {"hanging": "true"}))

def rule_fountain(ctx: BuildContext, cx: int, cy: int, cz: int):
    """A 5×5 fountain with a central water pillar."""
    stone_mat = ctx.palette["foundation"]
    wall_mat  = ctx.palette["wall"]
    light_mat = ctx.palette.get("light", "minecraft:lantern")

    x, y, z = cx - 2, cy, cz - 2

    # Foundation
    fill_cuboid(ctx.buffer, x, y - 4, z, x + 4, y - 1, z + 4, Block(stone_mat))

    # Basin
    fill_cuboid_wireframe(ctx.buffer, x, y, z, x + 4, y, z + 4, Block(stone_mat))
    fill_cuboid(ctx.buffer, x + 1, y, z + 1, x + 3, y, z + 3, Block("minecraft:water"))

    # Central water pillar
    fill_line(ctx.buffer, cx, y + 1, cz, cx, y + 3, cz, Block(wall_mat))
    ctx.place_block((cx, y + 4, cz), Block("minecraft:water"))

    # Corner lanterns
    for lx, lz in [(x, z), (x + 4, z), (x, z + 4), (x + 4, z + 4)]:
        ctx.place_block((lx, y + 1, lz), Block(light_mat))