"""
Terminal Rule: Window Carving
Styles: 'slit', 'standard', 'arched'
"""
from __future__ import annotations
from gdpc import Block
from palette.palette_system import palette_get
from structures.base.build_context import BuildContext

def rule_window(ctx, x, y, z, style="standard", facing="north", offset=0, door_offset=None, wall_len=5):
    
    if door_offset is not None and offset == door_offset:
        return
    
    mat_glass = palette_get(ctx.palette, "window", "minecraft:glass_pane")
    mat_stair = palette_get(ctx.palette, "roof", "minecraft:oak_stairs")

    # Coordinate calculation
    dx, dz = (offset, 0) if facing in ["north", "south"] else (0, offset)
    rx, rz = x + dx, z + dz

    if style == "arched":
        _design_arched(ctx, rx, y, rz, facing, mat_glass, mat_stair)
    elif style == "slit":
        _design_slit(ctx, rx, y, rz, mat_glass)
    else:
        _design_standard(ctx, rx, y, rz, mat_glass)

# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _design_slit(ctx, x, y, z, mat_glass):
    """Single vertical block for defense or towers."""
    ctx.place_block((x, y, z), Block(mat_glass))

def _design_standard(ctx, x, y, z, mat_glass):
    """Basic 1x2 window."""
    ctx.place_block((x, y, z), Block(mat_glass))
    ctx.place_block((x, y + 1, z), Block(mat_glass))

def _design_arched(ctx, x, y, z, facing, mat_glass, mat_stair):
    """A glass block with an upside-down stair on top to create an arch."""
    ctx.place_block((x, y, z), Block(mat_glass))
    # 'half': 'top' makes the stair upside down
    ctx.place_block((x, y + 1, z), Block(mat_stair, {"half": "top", "facing": facing}))