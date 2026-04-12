import random
from gdpc import Block
from structures.base.build_context import BuildContext
from palette.palette_system import palette_get

def rule_market_supports(ctx: BuildContext, x: int, y: int, z: int, w: int, d: int, h: int):
    """Places corner fence posts and a support frame."""
    fence = palette_get(ctx.palette, "fence", "minecraft:spruce_fence")
    # Front pillars (slightly shorter for canopy slope)
    for dy in range(1, h):
        ctx.place_block((x, y + dy, z), Block(fence))
        ctx.place_block((x + w - 1, y + dy, z), Block(fence))
    # Back pillars
    for dy in range(1, h + 1):
        ctx.place_block((x, y + dy, z + d - 1), Block(fence))
        ctx.place_block((x + w - 1, y + dy, z + d - 1), Block(fence))

def rule_market_counter(ctx: BuildContext, x: int, y: int, z: int, w: int, d: int):
    """Builds a vendor counter with barrels and slabs."""
    slab = palette_get(ctx.palette, "floor_slab", "minecraft:spruce_slab")
    # Counter front
    for dx in range(1, w - 1):
        ctx.place_block((x + dx, y + 1, z + 1), Block(slab, {"type": "top"}))
    # Side barrels/storage
    ctx.place_block((x + 1, y + 1, z + 2), Block("minecraft:barrel", {"facing": "up"}))

def rule_market_canopy(ctx: BuildContext, x: int, y: int, z: int, w: int, d: int, h: int):
    """Striped wool canopy with a forward slope."""
    colors = ["red", "blue", "yellow", "orange", "lime", "purple"]
    primary = f"minecraft:{random.choice(colors)}_wool"
    secondary = "minecraft:white_wool"
    
    for dx in range(w):
        # Alternate stripes based on X coordinate
        mat = primary if dx % 2 == 0 else secondary
        for dz in range(d):
            # Slope: Back (z=d-1) is height h+1, Front (z=0) is height h
            dy = h + 1 if dz >= (d // 2) else h
            ctx.place_block((x + dx, y + dy, z + dz), Block(mat))
            
            # Front overhang "flap" using carpet
            if dz == 0:
                carpet = mat.replace("_wool", "_carpet")
                ctx.place_block((x + dx, y + dy, z - 1), Block(carpet))