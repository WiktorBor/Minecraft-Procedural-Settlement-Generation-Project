from __future__ import annotations
from gdpc import Block
from structures.base.build_context import BuildContext
from structures.grammar.belfry_grammar import rule_belfry

_FOUND_DEPTH: int = 6 

def rule_fortification(
        ctx: BuildContext, 
        x: int, top_y: int, z: int, 
        length: int, 
        hmap, area, t_boxes, b_boxes, horizontal: bool, fill_walkway: bool = False):
    
    # 1. Setup Materials
    log_mat   = ctx.palette.get("accent", "minecraft:stripped_dark_oak_log")
    wall_mat  = ctx.palette.get("wall", "minecraft:stone_bricks")      
    plank_mat = ctx.palette.get("floor", "minecraft:dark_oak_planks") 
    found_mat = ctx.palette.get("foundation", "minecraft:cobblestone")

    arch_base_y = top_y - 5
    
    # 2. Continuous Step-by-Step Loop
    # This ensures the wall is solid even if length is not a multiple of 6
    for step in range(length + 1):
        px = x + step if horizontal else x
        pz = z if horizontal else z + step
        
        # LOCAL CLIPPING: Skip only the blocks that hit a building/tower
        if _in_box(px, pz, t_boxes) or _in_box(px, pz, b_boxes):
            continue

        # 3. Sample Ground
        li = max(0, min(hmap.shape[0] - 1, px - area.x_from))
        lj = max(0, min(hmap.shape[1] - 1, pz - area.z_from))
        gy = int(hmap[li, lj])

        # 4. BUILD SOLID BASE
        # Foundation
        for py in range(gy - _FOUND_DEPTH, gy):
            ctx.place_block((px, py, pz), Block(found_mat))
        # Solid Wall
        for py in range(gy, arch_base_y + 1):
            ctx.place_block((px, py, pz), Block(wall_mat))

        # 5. BUILD DECORATIVE TOP
        if step % 6 == 0:
            # Pillar logic every 6 blocks
            for py in range(arch_base_y + 1, top_y):
                ctx.place_block((px, py, pz), Block(log_mat))
            ctx.place_block((px, top_y, pz), Block(plank_mat))
            
            # Trigger Belfry Arch for the segment following this pillar
            if step + 6 <= length:
                ax, az = (px + 1, pz) if horizontal else (px, pz + 1)
                bw, bd = (5, 1) if horizontal else (1, 5)
                rule_belfry(ctx, ax, arch_base_y, az, bw, bd, h=4, style="arched")
        else:
            # Walkway Fill between pillars
            ctx.place_block((px, top_y - 1, pz), Block(wall_mat))
            ctx.place_block((px, top_y, pz), Block(plank_mat))

def _in_box(wx: int, wz: int, boxes: list) -> bool:
    for x0, z0, x1, z1 in boxes:
        if x0 <= wx <= x1 and z0 <= wz <= z1:
            return True
    return False