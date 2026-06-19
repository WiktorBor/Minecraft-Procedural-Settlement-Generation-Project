from gdpc.block import Block

def rule_ceiling(ctx, x, y, z, style="beams", facing="north", length=1):
    """
    Handles the internal top surface of a room.
    """
    mat_plank = ctx.palette.get("ceiling", "minecraft:spruce_planks")
    mat_log = ctx.palette.get("accent", "minecraft:dark_oak_log")
    mat_slab = ctx.palette.get("slab", "minecraft:spruce_slab")

    if style == "beams":
        _design_beams(ctx, x, y, z, facing, length, mat_plank, mat_log)
    elif style == "coffered":
        _design_coffered(ctx, x, y, z, facing, length, mat_log, mat_slab)
    else:
        # Simple flat ceiling
        for i in range(length):
            _place_strip(ctx, x, y, z, facing, i, mat_plank)

def _design_coffered(ctx, x, y, z, facing, length, mat_grid, mat_panel):
    """Creates a line of 'Beam, Slab, Slab, Beam'."""
    ax, az = (1, 0) if facing in ["north", "south"] else (0, 1)
    for i in range(length):
        # Every 3rd block across the width is a log
        mat = mat_grid if i % 3 == 0 else mat_panel
        ctx.place_block((x + i*ax, y, z + i*az), Block(mat))

def _design_beams(ctx, x, y, z, facing, length, mat_bg, mat_beam):
    """Exposed structural beams every 2 blocks."""
    for i in range(length):
        # Place the main ceiling plank
        mat = mat_beam if i % 2 == 0 else mat_bg
        _place_strip(ctx, x, y, z, facing, i, mat)

def _place_strip(ctx, x, y, z, facing, offset, mat):
    dx, dz = (offset, 0) if facing in ["north", "south"] else (0, offset)
    ctx.place_block((x + dx, y, z + dz), Block(mat))