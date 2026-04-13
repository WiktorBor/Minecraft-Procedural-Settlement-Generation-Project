import random
from gdpc import Block
from structures.orchestrators.primitives.wall import build_wall
from structures.orchestrators.primitives.floor import build_floor
from structures.orchestrators.primitives.roof import build_roof
from structures.orchestrators.primitives.door import build_door
from structures.orchestrators.primitives.window import build_windows
from structures.orchestrators.primitives.ceiling import build_ceiling
from structures.base.build_context import BuildContext #
from structures.house.house_scorer import HouseParams

def rule_house(
    ctx: BuildContext, 
    x: int, y: int, z: int, 
    w: int, d: int, 
    params: HouseParams
) -> None:
    """
    Grammar rule with integrated decorations.
    The house builds strictly axis-aligned.
    """
    # 1. Structural Shell
    actual_wall_h = 5 if params.structure_role == "cottage" else params.wall_h

    build_wall(ctx, x, y, z, w, actual_wall_h, d, structure_role=params.structure_role)
    build_floor(ctx, x + 1, y, z + 1, w - 2, d - 2, structure_role=params.structure_role)
    
    door_side = build_door(ctx, x, y + 1, z, w, d, connector_side=params.bridge_side, structure_role=params.structure_role)
    build_windows(ctx, x, y, z, w, d, bridge_side=params.bridge_side, door_side=door_side, structure_role=params.structure_role)
    
    ceiling_y = y + actual_wall_h
    build_ceiling(ctx, x, ceiling_y, z, w, d, structure_role=params.structure_role)
    build_roof(ctx, x, y, z, w, actual_wall_h, d, structure_role=params.structure_role, connector_side=params.bridge_side)

    # 2. Integrated Details
    door_z = z # Default facade for north-facing door
    door_x = x + (w // 2)
    
    # Exterior: Lantern above the door
    ctx.place_light((door_x, y + actual_wall_h - 1, door_z + 1), key="light", hanging=True)

    # Exterior: Porch fence posts
    if params.has_porch:
        for fx in (door_x + 1, door_x - 1):
            ctx.place((fx, y + 1, door_z + d), "fence")
            ctx.place((fx, y + 2, door_z + d), "fence")
            ctx.place((fx, y, door_z + d), "striped_log")

    ctx.place_block((door_x, y, door_z + d), Block("minecraft:spruce_stairs", {"facing": "north", "half": "bottom"}))

    # Interior: Bed and Crafting Table
    ctx.place_block((x + 2, y + 1, z + 2), Block("minecraft:red_bed", {"facing": "north", "part": "foot"}))
    ctx.place_block((x + w - 3, y + 1, z + 1), Block("minecraft:crafting_table"))

    # Chimney: Rising from ceiling through the roof
    if params.has_chimney:
        chim_x, chim_z = x + 1, z + 1
        top_y = ceiling_y + (max(w, d) // 2) + 1
        for cy in range(ceiling_y, top_y):
            ctx.place((chim_x, cy, chim_z), "foundation")
        ctx.place_block((chim_x, top_y, chim_z), Block("minecraft:campfire", {"lit": "true"}))