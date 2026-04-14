from gdpc.block import Block

def rule_stair(ctx, x, y, z, height, landing_len, facing="north", style="straight", exit_facing="north"):
    stair_mat = ctx.palette.get("roof", "minecraft:spruce_stairs")
    support_mat = ctx.palette.get("foundation", "minecraft:stone_bricks")

    if style == "straight":
        _design_straight(ctx, x, y, z, height, facing, stair_mat, support_mat, landing_len)
    elif style == "spiral":
        _design_spiral(ctx, x, y, z, height, stair_mat, support_mat, exit_facing, landing_len)
    elif style == "ladder":
        _design_ladder(ctx, x, y, z, height, facing)

def _design_straight(ctx, x, y, z, height, facing, mat, support, landing_len):

    if facing == "north":   
        dx, dz = 0, -1
    elif facing == "south": 
        dx, dz = 0, 1
    elif facing == "east":  
        dx, dz = 1, 0
    elif facing == "west":  
        dx, dz = -1, 0

    for i in range(height):
        # The Stair
        ctx.place_block((x + i*dx, y + i, z + i*dz), Block(f"{mat}[facing={facing}]"))
        # The Support
        for dy in range(1, i + 1):
            ctx.place_block((x + i*dx, y + i - dy, z + i*dz), Block(support))

    top_y = y + height - 1
    for j in range(1, landing_len):
        lx = x + (height + j - 1) * dx
        lz = z + (height + j - 1) * dz
        
        # Use a full block or slab for the landing
        # Slabs need [type=bottom] to sit flush with the top of the stair
        ctx.place_block((lx, top_y, lz), Block(support)) 

def _design_spiral(ctx, x, y, z, height, mat, support, exit_facing, landing_len):
    """
    Builds a spiral staircase starting from the top exit and winding down to the floor.
    x, y, z is the bottom corner, but we calculate from y + height.
    """
    # Map exit_facing to the starting index in our anticlockwise orbit
    # This ensures the TOP step aligns with the second-floor door/hallway
    exit_map = {"north": 6, "south": 1, "east": 3, "west": 7}
    exit_idx = exit_map.get(exit_facing, 7)

    # Anticlockwise offsets (Left -> Bottom -> Right -> Top)
    offsets = [(0,0), (0,1), (0,2), (1,2), (2,2), (2,1), (2,0), (1,0)]
    # Match facings to these offsets so they climb UP (or descend DOWN correctly)
    facings = ["south", "south", "east", "east", "north", "north", "west", "west"]

    # 1. Build the Central Pillar
    for dy in range(height):
        ctx.place_block((x, y + dy, z + 1), Block(support))

    # 2. Build from Top to Bottom
    top_y = y + height - 1
# 2. The STRAIGHT Landing (Extending OUTSIDE the 3x3)
    # dx, dz determines the direction the straight line grows
    ldx, ldz = 0, 0
    if exit_facing == "north": ldx = 1
    elif exit_facing == "south": ldx = -1
    elif exit_facing == "east":  ldz = -1
    elif exit_facing == "west":  ldz = 1

    # Starting point for the landing is the edge of the 3x3
    lx_start, lz_start = x, z 

    for j in range(landing_len):
        curr_lx = lx_start + (j * ldx)
        curr_lz = lz_start + (j * ldz)
        ctx.place_block((curr_lx, top_y, curr_lz), Block(support))
        
    # We loop from (height - 1) down to 0
    for dy in range(height - 1, -1, -1):
        # Calculate index based on how many steps we are away from the top
        # As dy decreases, we move backwards through the orbit
        steps_from_top = (height) - dy
        idx = (exit_idx - steps_from_top) % 8
        
        ox, oz = offsets[idx]
        f = facings[idx]
        
        curr_x, curr_y, curr_z = x + ox - 1, y + dy, z + oz
        
        # Place the stair
        ctx.place_block((curr_x, curr_y, curr_z), Block(f"{mat}[facing={f}]"))
        
        # Support under the step
        for fill_y in range(dy):
            ctx.place_block((curr_x, y + fill_y, curr_z), Block(support))
    
def _design_ladder(ctx, x, y, z, height, facing):
    for i in range(height):
        ctx.place_block((x, y + i, z), Block(f"minecraft:ladder[facing={facing}]"))