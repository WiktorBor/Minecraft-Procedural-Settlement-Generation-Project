from __future__ import annotations
from gdpc import Block
from structures.base.build_context import BuildContext
from structures.grammar.belfry_grammar import rule_belfry

_FOUND_DEPTH: int = 6 #

def rule_fortification(
        ctx: BuildContext, 
        x: int, top_y: int, z: int, 
        length: int, 
        hmap, area, t_boxes, b_boxes, horizontal: bool, fill_walkway: bool = False):
    log_mat = ctx.palette.get("accent", "minecraft:stripped_dark_oak_log")
    wall_mat = ctx.palette.get("wall", "minecraft:stone_bricks")      # The stone fill
    plank_mat = ctx.palette.get("floor", "minecraft:dark_oak_planks") # The top walkway
    
    n_arches = max(1, length // 6)
    
    for i in range(n_arches + 1):
        px = x + (i * 6) if horizontal else x
        pz = z if horizontal else z + (i * 6)
        
        if _in_box(px, pz, t_boxes) or _in_box(px, pz, b_boxes):
            continue

        # Logic for the "fill" line between parallel walls
        if fill_walkway:
            for step in range(6 if i < n_arches else 1):
                fx, fz = (px + step, pz) if horizontal else (px, pz + step)
                ctx.place_block((fx, top_y, fz), Block(plank_mat))
            continue

        # 1. Main Pillars
        li = max(0, min(hmap.shape[0] - 1, px - area.x_from))
        lj = max(0, min(hmap.shape[1] - 1, pz - area.z_from))
        gy = int(hmap[li, lj])

        for py in range(gy - _FOUND_DEPTH, top_y):
            ctx.place_block((px, py, pz), Block(log_mat))
        
        ctx.place_block((px, top_y, pz), Block(plank_mat))

        # 2. Build the Arches and the Stone Fill
        if i < n_arches:
            ax, az = (px + 1, pz) if horizontal else (px, pz + 1)
            bw, bd = (5, 1) if horizontal else (1, 5)
            
            # Place the arch structure
            rule_belfry(ctx, ax, top_y - 5, az, bw, bd, h=4, style="arched")
            
            # FILL: This matches the loop from your successful file
            for step in range(5):
                fx, fz = (ax + step, az) if horizontal else (ax, az + step)
                # Fill the layer immediately above the decorative arch blocks
                ctx.place_block((fx, top_y - 1, fz), Block(wall_mat))
                # Cap the top layer with planks to create a walkway
                ctx.place_block((fx, top_y, fz), Block(plank_mat))
    
def _in_box(wx: int, wz: int, boxes: list) -> bool:
    """Checks if a coordinate (wx, wz) is inside any of the provided bounding boxes."""
    for x0, z0, x1, z1 in boxes:
        if x0 <= wx <= x1 and z0 <= wz <= z1:
            return True
    return False