"""
Terminal Rule: Floor Design
Standardized Dispatcher Pattern
"""
from __future__ import annotations
from gdpc import Block
from palette.palette_system import palette_get
from structures.base.build_context import BuildContext

def rule_floor(ctx: BuildContext, x, y, z, w, d, style="plain"):
    """
    DISPATCHER: Maps the style string to the specific logic helper.
    """
    mat_primary   = ctx.palette.get("floor")
    mat_secondary = ctx.palette.get("accent")
    mat_moss      = ctx.palette.get("moss", mat_primary)
    mat_extra     = ctx.palette.get("foundation")

    if style == "checker":
        _design_checker(ctx, x, y, z, w, d, mat_primary, mat_moss)
    elif style == "rug":
        _design_rug(ctx, x, y, z, w, d, mat_primary, mat_moss)
    elif style == "bordered":
        _design_bordered(ctx, x, y, z, w, d, mat_primary, mat_secondary)
    elif style == "parquet":
        _design_parquet(ctx, x, y, z, w, d, mat_primary, mat_secondary)
    elif style == "radial":
        _design_radial(ctx, x, y, z, w, d, mat_primary, mat_extra)
    else:
        _design_plain(ctx, x, y, z, w, d, mat_primary)

# --- NEW COMPONENT: Pillar Bases ---
def rule_floor_supports(ctx, x, y, z, w, d, material=None):
    """Reinforces the 4 corners of the floor where pillars sit."""
    mat = material if material else ctx.palette.get("foundation")
    corners = [(0, 0), (w - 1, 0), (0, d - 1), (w - 1, d - 1)]
    for dx, dz in corners:
        ctx.place_block((x + dx, y, z + dz), Block(mat))

# --- Internal builders ---
def _design_plain(ctx, x, y, z, w, d, mat):
    for dx in range(w):
        for dz in range(d):
            ctx.place_block((x + dx, y, z + dz), Block(mat))

def _design_checker(ctx, x, y, z, w, d, mat1, mat2):
    for dx in range(w):
        for dz in range(d):
            mat = mat1 if (dx + dz) % 2 == 0 else mat2
            ctx.place_block((x + dx, y, z + dz), Block(mat))

def _design_rug(ctx, x, y, z, w, d, mat_base, mat_rug):
    for dx in range(w):
        for dz in range(d):
            is_inner = (1 <= dx < w - 1 and 1 <= dz < d - 1)
            mat = mat_rug if is_inner else mat_base
            ctx.place_block((x + dx, y, z + dz), Block(mat))

def _design_bordered(ctx, x, y, z, w, d, mat_center, mat_border):
    for dx in range(w):
        for dz in range(d):
            is_border = (dx == 0 or dx == w - 1 or dz == 0 or dz == d - 1)
            mat = mat_border if is_border else mat_center
            ctx.place_block((x + dx, y, z + dz), Block(mat))

def _design_parquet(ctx, x, y, z, w, d, mat1, mat2):
    for dx in range(w):
        for dz in range(d):
            mat = mat1 if ((dx // 2) + (dz // 2)) % 2 == 0 else mat2
            ctx.place_block((x + dx, y, z + dz), Block(mat))

def _design_radial(ctx, x, y, z, w, d, mat_main, mat_center):
    mid_x, mid_z = w // 2, d // 2
    for dx in range(w):
        for dz in range(d):
            is_mid = abs(dx - mid_x) <= 1 and abs(dz - mid_z) <= 1
            mat = mat_center if is_mid else mat_main
            ctx.place_block((x + dx, y, z + dz), Block(mat))