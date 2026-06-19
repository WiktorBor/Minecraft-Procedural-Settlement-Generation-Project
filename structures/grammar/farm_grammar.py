from __future__ import annotations
import random
from gdpc import Block
from structures.base.build_context import BuildContext
from structures.base.geometry import fill_cuboid, fill_cuboid_wireframe, fill_line

# Crop configuration from original builder
_CROP_PAIRS = [
    ("minecraft:wheat",   "minecraft:carrots"),
    ("minecraft:wheat",   "minecraft:potatoes"),
    ("minecraft:carrots", "minecraft:beetroots"),
]

_CROP_MAX_AGE = {"minecraft:beetroots": 3}

def rule_farm(ctx: BuildContext, x: int, y: int, z: int, w: int, d: int):
    """
    The assembly rule for a Farm.
    """
    # Material Mapping from Palette
    basin_block = ctx.palette.get("accent",     "minecraft:oak_log")
    found_block = ctx.palette.get("foundation", "minecraft:cobblestone")
    light_block = ctx.palette.get("light",      "minecraft:lantern")
    
    crops_left, crops_right = random.choice(_CROP_PAIRS)
    channel_x = x + w // 2

    # 1. Foundation: Sinks into the ground
    fill_cuboid(
        ctx.buffer,
        x, y - 6, z, x + w - 1, y - 2, z + d - 1,
        Block(found_block),
    )

    # 2. Frame: Base and perimeter
    fill_cuboid(
        ctx.buffer,
        x, y - 1, z, x + w - 1, y - 1, z + d - 1,
        Block(basin_block),
    )
    fill_cuboid_wireframe(
        ctx.buffer,
        x, y, z, x + w - 1, y, z + d - 1,
        Block(basin_block),
    )

    # 3. Interior: Farmland and Water
    fill_cuboid(
        ctx.buffer,
        x + 1, y, z + 1, x + w - 2, y, z + d - 2,
        Block("minecraft:farmland"),
    )
    fill_line(
        ctx.buffer,
        channel_x, y, z + 1, channel_x, y, z + d - 2,
        Block("minecraft:water"),
    )

    # 4. Crops: Determined by age
    _place_crops(ctx, x, y, z, w, d, channel_x, crops_left, crops_right)

    # 5. Lighting: Corners
    for lx, lz in [(x, z), (x + w - 1, z), (x, z + d - 1), (x + w - 1, z + d - 1)]:
        ctx.place_block((lx, y + 1, lz), Block(light_block))

def _place_crops(ctx, x, y, z, w, d, channel_x, left_type, right_type):
    """Helper to fill crop rows."""
    age_l = str(_CROP_MAX_AGE.get(left_type, 7))
    age_r = str(_CROP_MAX_AGE.get(right_type, 7))
    
    if channel_x - 1 >= x + 1:
        fill_cuboid(ctx.buffer, x + 1, y + 1, z + 1, channel_x - 1, y + 1, z + d - 2, 
                    Block(left_type, {"age": age_l}))
    if channel_x + 1 <= x + w - 2:
        fill_cuboid(ctx.buffer, channel_x + 1, y + 1, z + 1, x + w - 2, y + 1, z + d - 2, 
                    Block(right_type, {"age": age_r}))