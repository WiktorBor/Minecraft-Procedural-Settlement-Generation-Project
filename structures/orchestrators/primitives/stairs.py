from gdpc.block import Block
from structures.grammar.stairs_grammar import rule_stair
from structures.base.build_context import BuildContext

def build_stairs(
        ctx: BuildContext, 
        x: int, y: int, z: int, 
        w: int, d: int, height: int, 
        structure_role="main", 
        landing_len=0, 
        exit_facing=None) -> None:
    
    if exit_facing is None:
        return
    # 1. Choose Travel Direction (where you want to go UP)
    # If the room is deeper (Z), walk North/South. If wider (X), walk East/West.
    travel_dir = "north" if d >= w else "west"

    # 2. Snap Start Point to the correct corner so we stay INSIDE
    # We want to start 2 blocks away from the 'far' wall so we can climb towards the center.
    if travel_dir == "north":
        # Climbing North (-Z), so we must start at the SOUTH end of the room
        sx, sz = x, z + d - 3 
    elif travel_dir == "south":
        # Climbing South (+Z), so we start at the NORTH end
        sx, sz = x, z + 2
    elif travel_dir == "west":
        # Climbing West (-X), so we start at the EAST end
        sx, sz = x + w - 2, z + 2
    elif travel_dir == "east":
        # Climbing East (+X), so we start at the WEST end
        sx, sz = x, z + 2
    
    # Logic to determine style and bounds
    if structure_role == "annex":
        style = "spiral"
        # Spiral footprint is 3x3
        clear_w, clear_d = 3, 3
        # Adjust start so 3x3 stays inside (assuming 5x5 min room)
        sx, sz = x + 1, z + 1 
    else:
        style = "straight"
        # Straight footprint depends on height (1 block per step)
        # Assuming travel_dir is North/South for this example
        clear_w, clear_d = 1, height + 2 # +2 for the landing
        # Adjust start for 'North' climb (starting at South wall)
        sz = z + d - 3

    # 1. Use the helper to punch the hole
    _clear_stairwell(ctx, sx, y, sz, clear_w, clear_d, height)
    
    # 4. Build the stairs
    rule_stair(ctx, sx, y, sz, height, landing_len, facing=travel_dir, style=style, exit_facing=exit_facing)


def _clear_stairwell(ctx, x, y, z, w, d, height):
    """
    Helper to carve a hole in the ceiling and ensure head clearance.
    Clears from the ceiling level up to two blocks above for the player.
    """
    for dx in range(w):
        for dz in range(d):
            # We clear the ceiling block (y + height - 1) 
            # and the space above it (y + height, y + height + 1)
            for dy in range(height - 1, height + 2):
                ctx.place_block((x + dx, y + dy, z + dz), Block("minecraft:air"))