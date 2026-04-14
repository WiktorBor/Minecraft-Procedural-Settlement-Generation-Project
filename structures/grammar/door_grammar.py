"""
Terminal Rule: Door Placement
Styles: 'simple', 'arched', 'heavy'
"""
from __future__ import annotations
from gdpc import Block
from palette.palette_system import palette_get
from structures.base.build_context import BuildContext

def rule_door(ctx: BuildContext, x, y, z, style="simple", facing="north", offset=0):
    """
    DISPATCHER: Maps the style string to the specific door logic.
    """
    # 1. COMPUTE OFFSET: Translate local wall-start to actual world position
    dx, dz = (offset, 0) if facing in ["north", "south"] else (0, offset)
    rx, rz = x + dx, z + dz

    # 2. Palette Mapping
    # Minecraft doors are split into 'top' and 'bottom' halves
    mat_door = palette_get(ctx.palette, "door", "minecraft:oak_door")
    mat_frame = palette_get(ctx.palette, "accent", "minecraft:stone_bricks")

    # 3. Routing Logic
    if style == "arched":
        _design_arched_door(ctx, rx, y, rz, facing, mat_door, mat_frame)
    elif style == "heavy":
        _design_heavy_door(ctx, rx, y, rz, facing, mat_door)
    else:
        _design_simple_door(ctx, rx, y, rz, facing, mat_door)

# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _design_simple_door(ctx, x, y, z, facing, mat):
    """A standard 1x2 wooden door."""
    # Bottom half
    ctx.place_block((x, y, z), Block(mat, {"half": "lower", "facing": facing}))
    # Top half
    ctx.place_block((x, y + 1, z), Block(mat, {"half": "upper", "facing": facing}))

def _design_arched_door(ctx, x, y, z, facing, mat_door, mat_frame):
    """A door with a decorative frame (arch) around it."""
    # The Door itself
    _design_simple_door(ctx, x, y, z, facing, mat_door)
    
    # The Frame (placed around the door)
    # This logic assumes the door is in a wall; it replaces blocks at y, y+1, y+2
    dx, dz = (1, 0) if facing in ["north", "south"] else (0, 1)
    
    # Sides of the frame
    ctx.place_block((x + dx, y, z + dz), Block(mat_frame))
    ctx.place_block((x + dx, y + 1, z + dz), Block(mat_frame))
    ctx.place_block((x - dx, y, z - dz), Block(mat_frame))
    ctx.place_block((x - dx, y + 1, z - dz), Block(mat_frame))
    
    # Top of the frame (The lintel)
    ctx.place_block((x, y + 2, z), Block(mat_frame))

def _design_heavy_door(ctx, x, y, z, facing, mat):
    """A double-door setup for main entrances."""
    dx, dz = (1, 0) if facing in ["north", "south"] else (0, 1)
    # Left Door
    ctx.place_block((x, y, z), Block(mat, {"half": "lower", "facing": facing, "hinge": "left"}))
    ctx.place_block((x, y + 1, z), Block(mat, {"half": "upper", "facing": facing, "hinge": "left"}))
    # Right Door
    ctx.place_block((x + dx, y, z + dz), Block(mat, {"half": "lower", "facing": facing, "hinge": "right"}))
    ctx.place_block((x + dx, y + 1, z + dz), Block(mat, {"half": "upper", "facing": facing, "hinge": "right"}))