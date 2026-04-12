import math
from gdpc import Block
from structures.base.build_context import BuildContext
from palette.palette_system import palette_get

def rule_plaza_floor(ctx: BuildContext, cx: int, cy: int, cz: int, radius: int, clear_height: int):
    """Circular stone floor with the original XOR-based stone mix."""
    # Original _STONE_MIX logic
    stone_mix = ["minecraft:stone_bricks", "minecraft:cobblestone", "minecraft:andesite"]
    
    for ix in range(cx - radius, cx + radius + 1):
        for iz in range(cz - radius, cz + radius + 1):
            if math.sqrt((ix - cx) ** 2 + (iz - cz) ** 2) <= radius:
                # Original material selection: (ix ^ iz) % len
                b_type = stone_mix[(ix ^ iz) % len(stone_mix)]
                ctx.place_block((ix, cy, iz), Block(b_type))
                # Original clearing logic
                for iy in range(cy + 1, cy + clear_height):
                    ctx.place_block((ix, iy, iz), Block("minecraft:air"))

def rule_grand_spire(ctx: BuildContext, cx: int, cy: int, cz: int, radius: int):
    """Refined Grand Spire with basin rings and tiered mossy column."""
    r_outer_sq = radius * radius
    r_slab_sq  = (radius - 1) * (radius - 1)
    r_inner_sq = (radius - 2) * (radius - 2)

    # --- Outer water basin ring ---
    for dx in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            dist_sq = dx ** 2 + dz ** 2
            if r_inner_sq < dist_sq <= r_outer_sq:
                ctx.place_block((cx + dx, cy + 1, cz + dz), Block("minecraft:stone_bricks"))
                if dist_sq <= r_slab_sq:
                    ctx.place_block((cx + dx, cy + 2, cz + dz), Block("minecraft:stone_brick_slab"))
            elif dist_sq <= r_inner_sq:
                ctx.place_block((cx + dx, cy + 1, cz + dz), Block("minecraft:water"))

    # --- Central mossy pillar with tapering slab ledges ---
    tier_y_to_radius = {cy + 6: 4, cy + 12: 3, cy + 18: 2}

    for iy in range(cy + 1, cy + 22):
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                # Top layer is a plus shape (original detail)
                if iy == cy + 21 and abs(dx) == 1 and abs(dz) == 1:
                    continue
                ctx.place_block((cx + dx, iy, cz + dz), Block("minecraft:mossy_stone_bricks"))

        # Slab ledge logic
        if iy in tier_y_to_radius:
            pr_sq = tier_y_to_radius[iy] ** 2
            for dx in range(-tier_y_to_radius[iy], tier_y_to_radius[iy] + 1):
                for dz in range(-tier_y_to_radius[iy], tier_y_to_radius[iy] + 1):
                    dist_sq = dx**2 + dz**2
                    if dist_sq <= pr_sq and not (abs(dx) <= 1 and abs(dz) <= 1):
                        ctx.place_block((cx + dx, iy, cz + dz), 
                                        Block("minecraft:stone_brick_slab", {"type": "top"}))

    # --- Cap Details ---
    ctx.place_block((cx, cy + 22, cz), Block("minecraft:water"))
    ctx.place_block((cx, cy + 23, cz), Block("minecraft:oak_trapdoor", {"open": "false"}))
    ctx.place_block((cx, cy + 24, cz), Block("minecraft:glowstone"))

def rule_small_fountain(ctx: BuildContext, cx: int, cy: int, cz: int, radius: int):
    """Tiered small fountain with internal lighting."""
    # The 'Growing Rings' logic from the original file
    tiers = [
        (radius - 1, 1),
        (max(1, int((radius - 1) * 0.7)), 2),
        (max(1, int((radius - 1) * 0.4)), 3),
    ]
    for r, h in tiers:
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if dx**2 + dz**2 <= r**2:
                    ctx.place_block((cx + dx, cy + h, cz + dz), Block("minecraft:smooth_stone"))

    # Basin and Lighting
    basin_r = max(1, int(tiers[-1][0] * 0.8))
    for dx in range(-basin_r, basin_r + 1):
        for dz in range(-basin_r, basin_r + 1):
            if dx**2 + dz**2 <= basin_r**2:
                ctx.place_block((cx + dx, cy + 3, cz + dz), Block("minecraft:water"))
                ctx.place_block((cx + dx, cy + 2, cz + dz), Block("minecraft:sea_lantern"))