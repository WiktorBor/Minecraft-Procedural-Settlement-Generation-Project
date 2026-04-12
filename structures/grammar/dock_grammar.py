from gdpc import Block
from structures.base.build_context import BuildContext
from palette.palette_system import palette_get

def rule_dock_deck(ctx: BuildContext, x, y, z, w, d):
    """Lays the wooden plank surface."""
    planks = palette_get(ctx.palette, "floor", "minecraft:oak_planks")
    for dx in range(w):
        for dz in range(d):
            ctx.place_block((x + dx, y, z + dz), Block(planks))

def rule_dock_pillar(ctx: BuildContext, x, y, z, depth=4, bollard_h=1):
    """Builds a submerged log pillar with a stone cap (bollard) on top."""
    log = palette_get(ctx.palette, "foundation", "minecraft:dark_oak_log")
    stone = palette_get(ctx.palette, "accent", "minecraft:cobblestone")
    
    # Submerged Pillar
    for dy in range(1, depth + 1):
        ctx.place_block((x, y - dy, z), Block(log))
    
    # Bollard (above deck)
    for dy in range(1, bollard_h + 1):
        ctx.place_block((x, y + dy, z), Block(stone))

def rule_dock_railings(ctx: BuildContext, x, y, z, w, d, open_sides=None):
    """
    Places fences around the deck. 
    open_sides can contain 'north', 'south', 'east', 'west' to leave gaps.
    """
    fence = palette_get(ctx.palette, "fence", "minecraft:oak_fence")
    open_sides = open_sides or []
    
    for dx in range(w):
        if 'north' not in open_sides: # Back
            ctx.place_block((x + dx, y + 1, z), Block(fence))
        if 'south' not in open_sides: # Front
            ctx.place_block((x + dx, y + 1, z + d - 1), Block(fence))
            
    for dz in range(d):
        if 'west' not in open_sides: # Left
            ctx.place_block((x, y + 1, z + dz), Block(fence))
        if 'east' not in open_sides: # Right
            ctx.place_block((x + w - 1, y + 1, z + dz), Block(fence))