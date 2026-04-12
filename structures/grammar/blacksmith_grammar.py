from gdpc import Block
from structures.base.build_context import BuildContext
from structures.orchestrators.primitives.roof import build_roof
from structures.orchestrators.primitives.ceiling import build_ceiling
from structures.orchestrators.primitives.wall import build_wall
from structures.orchestrators.primitives.floor import build_floor

def rule_forge_work_area(ctx: BuildContext, x, y, z, w, d, h, forge_d):
    """The stone-based work area with pillars."""
    log = ctx.palette.get("foundation", "minecraft:dark_oak_log")

    build_floor(ctx, x, y, z, w, d, structure_role="forge_floor")

    enclosed_z = z + forge_d
    enclosed_d = d - forge_d

    build_wall(
        ctx, 
        x, y, enclosed_z, 
        w, h, enclosed_d, 
        structure_role="blacksmith",
        skip_sides={"north"}
    )

    # Open Porch Pillars
    for px in [0, w-1]:
        for dy in range(1, h):
            ctx.place_block((x + px, y + dy, z), Block(log))
    
    build_roof(ctx, x, y, z, w, 5, d, structure_role="forge_roof")
    build_ceiling(ctx, x - 1, y + h, z, w + 2, d, structure_role="forge_ceiling")

def rule_chimney(ctx: BuildContext, x, y, z, height):
    """Vertical chimney stack with campfire."""
    mat = ctx.palette.get("foundation", "minecraft:stone_bricks")
    for dy in range(height):
        ctx.place_block((x, y + dy, z), Block(mat))
    ctx.place_block((x, y + height, z), Block("minecraft:campfire"))