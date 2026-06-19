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
    The house builds strictly axis-aligned, but decorations adapt to the door side.
    """
    # 1. Structural Shell
    actual_wall_h = 5 if params.structure_role == "cottage" else params.wall_h

    build_wall(ctx, x, y, z, w, actual_wall_h, d, structure_role=params.structure_role)
    build_floor(ctx, x + 1, y, z + 1, w - 2, d - 2, structure_role=params.structure_role)
    
    # CAPTURE the door_side (returns "north", "south", "east", or "west")
    door_side = build_door(ctx, x, y + 1, z, w, d, connector_side=params.bridge_side, structure_role=params.structure_role)
    
    build_windows(ctx, x, y, z, w, d, bridge_side=params.bridge_side, door_side=door_side, structure_role=params.structure_role)
    
    ceiling_y = y + actual_wall_h
    build_ceiling(ctx, x, ceiling_y, z, w, d, structure_role=params.structure_role)
    build_roof(ctx, x, y, z, w, actual_wall_h, d, structure_role=params.structure_role, connector_side=params.bridge_side)

    # 2. Dynamic Integrated Details (The Debugged Section)
    cx, cz = x + (w // 2), z + (d // 2)

    # Default positions
    door_x, door_z = cx, cz
    stair_facing = "south"
    side_offsets = []

    if door_side == "north":
        door_x, door_z = cx, z
        stair_facing = "south"
        side_offsets = [(1, 0), (-1, 0)] 
    elif door_side == "south":
        door_x, door_z = cx, z + d - 1
        stair_facing = "north"
        side_offsets = [(1, 0), (-1, 0)]
    elif door_side == "west":
        door_x, door_z = x, cz
        stair_facing = "east"
        side_offsets = [(0, 1), (0, -1)]
    else: # east
        door_x, door_z = x + w - 1, cz
        stair_facing = "west"
        side_offsets = [(0, 1), (0, -1)]

    # --- Exterior: Lantern above the door ---
    ctx.place_light((door_x, y + actual_wall_h - 1, door_z - 1), key="light", hanging=True)

    # --- Exterior: Porch fence posts and Stairs ---
    if params.has_porch:
        # The Step
        ctx.place_block((door_x, y, door_z), Block("minecraft:spruce_stairs", {"facing": stair_facing}))
        
        # Flanking Posts
        for dx, dz in side_offsets:
            fx, fz = door_x + dx, door_z + dz
            ctx.place((fx, y + 1, fz + 1), "fence")
            ctx.place((fx, y + 2, fz + 1), "fence")
            ctx.place((fx, y, fz + 1), "striped_log")

    # 3. Interior Details (Coordinates fixed to be INSIDE walls)
    # Wall is at x and x+w-1. Interior starts at x+1.
    ctx.place_block((x + 1, y + 1, z + 2), Block("minecraft:red_bed", {"facing": "north", "part": "foot"}))
    ctx.place_block((x + 1, y + 1, z + 1), Block("minecraft:crafting_table"))

    # 4. Chimney (Rising from ceiling)
    if params.has_chimney:
        chim_x, chim_z = x + 2, z + 2 # Moved inward to ensure it's not in the wall
        top_y = ceiling_y + (max(w, d) // 2) + 2
        for cy in range(ceiling_y, top_y):
            ctx.place((chim_x, cy, chim_z), "foundation")
        ctx.place_block((chim_x, top_y, chim_z), Block("minecraft:campfire", {"lit": "true"}))