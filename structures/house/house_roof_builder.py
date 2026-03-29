"""
Roof builder for the house shape grammar.

Three roof types, all selected via ctx.roof_type:

  "pyramid"  — tapered dark_oak_stairs columns converging to a ridge slab.
               Matches the small_house.nbt reference exactly.

  "gabled"   — classic two-slope gable with stair steps + gable-end fill.
               Restored from the original grammar (working implementation).

  "cross"    — cross-gabled roof: main gable + one or two perpendicular
               dormer arms.  Restored from the original grammar.

All roof types share the same RoofCorners bounding box so the overhang
is defined in one place and consistent across types.
"""
from __future__ import annotations

import random

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from .house_context import Ctx


# ---------------------------------------------------------------------------
# Roof bounding box helper
# ---------------------------------------------------------------------------

class _RC:
    """Roof corners derived from ctx — 1-block overhang on all XZ sides."""
    def __init__(self, ctx: Ctx) -> None:
        overhang = 1
        self.rx0 = ctx.x - overhang
        self.rx1 = ctx.x + ctx.w + overhang   # exclusive
        self.rz0 = ctx.z - overhang
        self.rz1 = ctx.z + ctx.d + overhang   # exclusive
        self.ry  = ctx.roof_base_y

    @property
    def rw(self): return self.rx1 - self.rx0
    @property
    def rd(self): return self.rz1 - self.rz0
    @property
    def pitch_along_x(self): return self.rw <= self.rd
    @property
    def span(self): return self.rw if self.pitch_along_x else self.rd
    @property
    def length(self): return self.rd if self.pitch_along_x else self.rw
    @property
    def mid_x(self): return self.rx0 + self.rw // 2
    @property
    def mid_z(self): return self.rz0 + self.rd // 2


class RoofBuilder:

    def __init__(self, editor: Editor, palette: BiomePalette) -> None:
        self.editor  = editor
        self.palette = palette

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, ctx: Ctx) -> None:
        if ctx.roof_type == "pyramid":
            self._build_pyramid(ctx)
        elif ctx.roof_type == "cross":
            self._build_cross_gabled(ctx)
        else:
            self._build_gabled(ctx)


    # ------------------------------------------------------------------
    # Pyramid roof
    # ------------------------------------------------------------------

    def _build_pyramid(self, ctx: Ctx) -> None:
        """
        Builds a proper four-sided pyramid roof by tapering both X and Z 
        dimensions inward by 1 block per layer.
        """
        mat_stair  = ctx.palette["roof"]
        mat_slab   = palette_get(ctx.palette, "roof_slab", "minecraft:dark_oak_slab")

        # Start 1 block outside the wall footprint for the eave overhang
        x0, x1 = ctx.x - 1, ctx.x + ctx.w
        z0, z1 = ctx.z - 1, ctx.z + ctx.d
        
        base_y = ctx.roof_base_y
        # Total layers is half of the shortest span
        max_layers = min(ctx.w + 2, ctx.d + 2) // 2

        for layer in range(max_layers):
            y = base_y + layer
            
            # Current layer bounds
            cur_x0, cur_x1 = x0 + layer, x1 - layer
            cur_z0, cur_z1 = z0 + layer, z1 - layer

            # Stop if the dimensions collapse
            if cur_x0 > cur_x1 or cur_z0 > cur_z1:
                break

            # Draw the four sides of the current taper layer
            for x in range(cur_x0, cur_x1 + 1):
                ctx.editor.placeBlock((x, y, cur_z0), Block(mat_stair, {"facing": "south"}))
                ctx.editor.placeBlock((x, y, cur_z1), Block(mat_stair, {"facing": "north"}))

            for z in range(cur_z0, cur_z1 + 1):
                ctx.editor.placeBlock((cur_x0, y, z), Block(mat_stair, {"facing": "east"}))
                ctx.editor.placeBlock((cur_x1, y, z), Block(mat_stair, {"facing": "west"}))

        # Ridge / Peak: Fill the remaining gap at the top with slabs
        final_layer = max_layers
        ridge_y = base_y + final_layer
        for x in range(x0 + final_layer, x1 - final_layer + 1):
            for z in range(z0 + final_layer, z1 - final_layer + 1):
                ctx.editor.placeBlock((x, ridge_y, z), Block(mat_slab, {"type": "bottom"}))

    # ------------------------------------------------------------------
    # Gabled roof  (restored from original grammar)
    # ------------------------------------------------------------------

    def _build_gabled(self, ctx: Ctx, rc: _RC = None) -> None:
        mat_roof  = ctx.palette["roof"]
        roof_slab = palette_get(ctx.palette, "roof_slab", "minecraft:dark_oak_slab")

        if rc is None:
            rc = _RC(ctx)

        peak = (rc.span // 2)

        for layer in range(peak):
            for along in range(rc.length):
                if rc.pitch_along_x:
                    ctx.editor.placeBlock(
                        (rc.rx0 + layer, rc.ry + layer, rc.rz0 + along),
                        Block(mat_roof, {"facing": "east"}),
                    )
                    ctx.editor.placeBlock(
                        (rc.rx1 - 1 - layer, rc.ry + layer, rc.rz0 + along),
                        Block(mat_roof, {"facing": "west"}),
                    )
                else:
                    ctx.editor.placeBlock(
                        (rc.rx0 + along, rc.ry + layer, rc.rz0 + layer),
                        Block(mat_roof, {"facing": "south"}),
                    )
                    ctx.editor.placeBlock(
                        (rc.rx0 + along, rc.ry + layer, rc.rz1 - 1 - layer),
                        Block(mat_roof, {"facing": "north"}),
                    )

        # Ridge cap for odd span
        if rc.span % 2 == 1:
            ridge_y = rc.ry + peak
            if rc.pitch_along_x:
                ridge_pos = [(rc.mid_x, ridge_y, rc.rz0 + a) for a in range(rc.length)]
            else:
                ridge_pos = [(rc.rx0 + a, ridge_y, rc.mid_z) for a in range(rc.length)]
            ctx.editor.placeBlock(ridge_pos, Block(roof_slab, {"type": "bottom"}))

        # Gable ends
        if rc.pitch_along_x:
            self._build_gable_end(ctx, rc, peak, faces=[rc.rz0 + 1, rc.rz1 - 2])
        else:
            self._build_gable_end(ctx, rc, peak, faces=[rc.rx0 + 1, rc.rx1 - 2])

    def _build_gable_end(self, ctx: Ctx, rc: _RC, peak: int, faces: list[int]) -> None:
        mat_wall   = ctx.palette["wall"]
        mat_accent = ctx.palette["accent"]
        win_mat    = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")

        if rc.pitch_along_x:
            for gz in faces:
                for layer in range(peak):
                    for gx in range(rc.rx0 + layer + 1, rc.rx1 - 1 - layer):
                        ctx.editor.placeBlock((gx, rc.ry + layer, gz), Block(mat_wall))
                for gx in range(rc.rx0 + 1, rc.rx1 - 1):
                    ctx.editor.placeBlock((gx, rc.ry, gz), Block(mat_accent))
                if peak >= 3:
                    if rc.rw % 2 == 0:
                        ctx.editor.placeBlock((rc.mid_x - 1, rc.ry + 1, gz), Block(win_mat))
                        ctx.editor.placeBlock((rc.mid_x,     rc.ry + 1, gz), Block(win_mat))
                    else:
                        ctx.editor.placeBlock((rc.mid_x, rc.ry + 1, gz), Block(win_mat))
        else:
            for gx in faces:
                for layer in range(peak):
                    for gz in range(rc.rz0 + layer + 1, rc.rz1 - 1 - layer):
                        ctx.editor.placeBlock((gx, rc.ry + layer, gz), Block(mat_wall))
                for gz in range(rc.rz0 + 1, rc.rz1 - 1):
                    ctx.editor.placeBlock((gx, rc.ry, gz), Block(mat_accent))
                if peak >= 3:
                    if rc.rd % 2 == 0:
                        ctx.editor.placeBlock((gx, rc.ry + 1, rc.mid_z - 1), Block(win_mat))
                        ctx.editor.placeBlock((gx, rc.ry + 1, rc.mid_z),     Block(win_mat))
                    else:
                        ctx.editor.placeBlock((gx, rc.ry + 1, rc.mid_z), Block(win_mat))

    # ------------------------------------------------------------------
    # Cross-gabled roof
    # ------------------------------------------------------------------

    def _build_cross_gabled(self, ctx: Ctx) -> None:
        rc   = _RC(ctx)
        peak = rc.span // 2
        self._build_gabled(ctx, rc=rc)

        both     = random.random() < 0.6
        sides    = ["east", "west"] if rc.pitch_along_x else ["south", "north"]
        to_build = sides if both else [random.choice(sides)]
        for side in to_build:
            self._build_cross_arm(ctx, rc, peak, side)

    def _cross_arm_params(self, rc: _RC, peak: int, side: str) -> dict:
        if not rc.pitch_along_x:
            south = (side == "south")
            return dict(
                inner_start    = rc.rz1 - 1  if south else rc.rz0,
                inner_step     = -1           if south else  1,
                stair_range    = (lambda iz: range(iz + 1, rc.rz1)) if south else (lambda iz: range(rc.rz0, iz)),
                perp_a         = lambda layer: rc.rx0 + layer + 1,
                perp_b         = lambda layer: rc.rx1 - 2 - layer,
                facing_a       = "east",
                facing_b       = "west",
                shape_a        = "inner_left"  if south else "inner_right",
                shape_b        = "inner_right" if south else "inner_left",
                make_pos_inner = lambda perp, y, inner: (perp, y, inner),
                make_pos_arm   = lambda perp, y, along: (perp, y, along),
                make_pos_ridge = lambda r, ry: (rc.mid_x, ry, r),
                ridge_range    = range(rc.rz1 - peak, rc.rz1 + 1) if south else range(rc.rz0 + 1, rc.rz0 + peak - 1),
                gable_face     = rc.rz1 - 2  if south else rc.rz0 + 1,
                arm_rc         = _ArmRC(rc.rx0, rc.rx1, rc.rz0, rc.rz0 + rc.rw, rc.ry),
            )
        else:
            east = (side == "east")
            return dict(
                inner_start    = rc.rx1 - 1  if east else rc.rx0,
                inner_step     = -1           if east else  1,
                stair_range    = (lambda ix: range(ix + 1, rc.rx1)) if east else (lambda ix: range(rc.rx0, ix)),
                perp_a         = lambda layer: rc.rz0 + layer + 1,
                perp_b         = lambda layer: rc.rz1 - 2 - layer,
                facing_a       = "south",
                facing_b       = "north",
                shape_a        = "inner_left"  if east else "inner_right",
                shape_b        = "inner_right" if east else "inner_left",
                make_pos_inner = lambda perp, y, inner: (inner, y, perp),
                make_pos_arm   = lambda perp, y, along: (along, y, perp),
                make_pos_ridge = lambda r, ry: (r, ry, rc.mid_z),
                ridge_range    = range(rc.rx1 - peak + 1, rc.rx1) if east else range(rc.rx0 + 1, rc.rx0 + peak),
                gable_face     = rc.rx1 - 2  if east else rc.rx0 + 1,
                arm_rc         = _ArmRC(rc.rx0 - 1, rc.rx0 + rc.rd + 1, rc.rz0 + 1, rc.rz1 - 1, rc.ry),
            )

    def _build_cross_arm(self, ctx: Ctx, rc: _RC, peak: int, side: str) -> None:
        mat_roof  = ctx.palette["roof"]
        roof_slab = palette_get(ctx.palette, "roof_slab", "minecraft:dark_oak_slab")

        if peak < 2:
            return

        p = self._cross_arm_params(rc, peak, side)

        for layer in range(peak - 1):
            arm_y  = rc.ry + layer
            inner  = p["inner_start"] + p["inner_step"] * layer
            perp_a = p["perp_a"](layer)
            perp_b = p["perp_b"](layer)

            ctx.editor.placeBlock(
                p["make_pos_inner"](perp_a, arm_y, inner),
                Block(mat_roof, {"facing": p["facing_a"], "shape": p["shape_a"]}),
            )
            ctx.editor.placeBlock(
                p["make_pos_inner"](perp_b, arm_y, inner),
                Block(mat_roof, {"facing": p["facing_b"], "shape": p["shape_b"]}),
            )
            for along in p["stair_range"](inner):
                ctx.editor.placeBlock(
                    p["make_pos_arm"](perp_a, arm_y, along),
                    Block(mat_roof, {"facing": p["facing_a"]}),
                )
                ctx.editor.placeBlock(
                    p["make_pos_arm"](perp_b, arm_y, along),
                    Block(mat_roof, {"facing": p["facing_b"]}),
                )

        if rc.span % 2 == 1:
            ridge_y = rc.ry + peak - 1
            for r in p["ridge_range"]:
                ctx.editor.placeBlock(
                    p["make_pos_ridge"](r, ridge_y),
                    Block(roof_slab, {"type": "bottom"}),
                )

        self._build_gable_end(ctx, p["arm_rc"], peak, faces=[p["gable_face"]])


class _ArmRC:
    """Minimal RC-compatible object for cross arm gable ends."""
    def __init__(self, rx0, rx1, rz0, rz1, ry):
        self.rx0, self.rx1 = rx0, rx1
        self.rz0, self.rz1 = rz0, rz1
        self.ry = ry
    @property
    def rw(self): return self.rx1 - self.rx0
    @property
    def rd(self): return self.rz1 - self.rz0
    @property
    def pitch_along_x(self): return self.rw <= self.rd
    @property
    def mid_x(self): return self.rx0 + self.rw // 2
    @property
    def mid_z(self): return self.rz0 + self.rd // 2