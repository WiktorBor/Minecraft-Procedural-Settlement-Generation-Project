"""
structures/roofs/roof_builder.py
---------------------------------
Single canonical roof module for ALL structures.

Three roof types, selected via the `roof_type` string argument:

  "pyramid"  — four-sided tapered roof converging to a ridge slab at the peak.
  "gabled"   — classic two-slope gable with stair steps + gable-end fill.
  "cross"    — cross-gabled roof: main gable + perpendicular dormer arms.

All types share the same _RoofCorners bounding box so the 1-block overhang
is defined once and consistent across types.

Public API
----------
  build_roof(ctx, x, y, z, w, d, roof_type)  — dispatch to the right builder
  build_gabled_roof(ctx, rc)                  — direct gabled build (used by cross too)

Both take a BuildContext so palette lookups and rotation are automatic.
"""
from __future__ import annotations

import random

from gdpc import Block

from palette.palette_system import palette_get
from structures.base.build_context import BuildContext


# ---------------------------------------------------------------------------
# Roof bounding box — 1-block overhang on all XZ sides
# ---------------------------------------------------------------------------

class _RoofCorners:
    """
    Computes the roof bounding box from an anchor + footprint, applying a
    1-block overhang on every horizontal side.

    The pitch axis is chosen automatically: whichever span is shorter
    gets the ridge running along it.
    """

    def __init__(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        overhang: int = 1,
    ) -> None:
        self.rx0 = x - overhang
        self.rx1 = x + w + overhang    # exclusive
        self.rz0 = z - overhang
        self.rz1 = z + d + overhang    # exclusive
        self.ry  = y

    @property
    def rw(self) -> int:
        return self.rx1 - self.rx0

    @property
    def rd(self) -> int:
        return self.rz1 - self.rz0

    @property
    def pitch_along_x(self) -> bool:
        """True when the ridge runs along the Z axis (X is the short span)."""
        return self.rw <= self.rd

    @property
    def span(self) -> int:
        """Shorter horizontal dimension — determines peak height."""
        return self.rw if self.rw < self.rd else self.rd

    @property
    def length(self) -> int:
        """Longer horizontal dimension — determines ridge length."""
        return self.rd if self.pitch_along_x else self.rw

    @property
    def mid_x(self) -> int:
        return self.rx0 + self.rw // 2

    @property
    def mid_z(self) -> int:
        return self.rz0 + self.rd // 2


class _ArmRC:
    """Minimal _RoofCorners-compatible object for cross-arm gable ends."""
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

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_roof(
    ctx: BuildContext,
    x: int, y: int, z: int,
    w: int, d: int,
    roof_type: str = "gabled",
    cross_side: str | None = None,
) -> None:
    """
    Build a roof of the given type at (x, y, z) over a w×d footprint.

    The roof starts at y (the first block above the wall top / ceiling).
    A 1-block overhang is applied automatically on all sides.

    Args:
        ctx:        Build context carrying editor + palette.
        x, y, z:    Anchor corner of the building footprint (NOT the overhang).
        w, d:       Building footprint dimensions (walls, not including overhang).
        roof_type:  "pyramid", "gabled", or "cross".
        cross_side: For "cross" roofs, force a specific arm side
                    ("north"|"south"|"east"|"west"). None = random.
    """
    rc = _RoofCorners(x, y, z, w, d)
    if roof_type == "pyramid":
        _build_pyramid(ctx, x, y, z, w, d)
    elif roof_type == "cross":
        _build_cross_gabled(ctx, rc, side=cross_side)
    else:
        build_gabled_roof(ctx, rc)

# ---------------------------------------------------------------------------
# Pyramid
# ---------------------------------------------------------------------------

def _build_pyramid(
    ctx: BuildContext,
    x: int, y: int, z: int,
    w: int, d: int,
) -> None:
    """
    Four-sided pyramid roof, tapering both X and Z inward by 1 per layer.

    Starts 1 block outside the wall footprint (eave overhang) and
    converges to a slab peak.
    """
    mat_stair = palette_get(ctx.palette, "roof_stairs", "minecraft:stone_brick_stairs")
    mat_slab  = palette_get(ctx.palette, "roof_slab",   "minecraft:stone_brick_slab")

    x0, x1    = x - 1, x + w
    z0, z1    = z - 1, z + d
    base_y    = y
    max_layers = min(w + 2, d + 2) // 2

    for layer in range(max_layers):
        cur_y  = base_y + layer
        cur_x0 = x0 + layer
        cur_x1 = x1 - layer
        cur_z0 = z0 + layer
        cur_z1 = z1 - layer

        if cur_x0 > cur_x1 or cur_z0 > cur_z1:
            break

        for lx in range(cur_x0, cur_x1 + 1):
            ctx.place_block((lx, cur_y, cur_z0), Block(mat_stair, {"facing": "south"}))
            ctx.place_block((lx, cur_y, cur_z1), Block(mat_stair, {"facing": "north"}))
        for lz in range(cur_z0, cur_z1 + 1):
            ctx.place_block((cur_x0, cur_y, lz), Block(mat_stair, {"facing": "east"}))
            ctx.place_block((cur_x1, cur_y, lz), Block(mat_stair, {"facing": "west"}))

    # Peak slab(s)
    ridge_y = base_y + max_layers
    for px in range(x0 + max_layers, x1 - max_layers + 1):
        for pz in range(z0 + max_layers, z1 - max_layers + 1):
            ctx.place_block((px, ridge_y, pz), Block(mat_slab, {"type": "bottom"}))

# ---------------------------------------------------------------------------
# Gabled
# ---------------------------------------------------------------------------

def build_gabled_roof(ctx: BuildContext, rc: _RoofCorners) -> None:
    """
    Classic two-slope gabled roof from a pre-computed _RoofCorners object.

    Exposed publicly so the cross-gabled builder can call it for the main
    span, and so any structure can build a gabled roof without knowing the
    internal geometry.
    """
    mat_roof  = palette_get(ctx.palette, "roof_stairs", "minecraft:spruce_oak_stairs")
    mat_slab  = palette_get(ctx.palette, "roof_slab", "minecraft:spruce_oak_slab")
    peak      = rc.span // 2

    for layer in range(peak):
        for along in range(rc.length):
            if rc.pitch_along_x:
                ctx.place_block(
                    (rc.rx0 + layer,          rc.ry + layer, rc.rz0 + along),
                    Block(mat_roof, {"facing": "east"}),
                )
                ctx.place_block(
                    (rc.rx1 - 1 - layer,      rc.ry + layer, rc.rz0 + along),
                    Block(mat_roof, {"facing": "west"}),
                )
            else:
                ctx.place_block(
                    (rc.rx0 + along, rc.ry + layer, rc.rz0 + layer),
                    Block(mat_roof, {"facing": "south"}),
                )
                ctx.place_block(
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
        for pos in ridge_pos:
            ctx.place_block(pos, Block(mat_slab, {"type": "bottom"}))

    # Gable ends
    if rc.pitch_along_x:
        _build_gable_ends(ctx, rc, peak, faces=[rc.rz0 + 1, rc.rz1 - 2])
    else:
        _build_gable_ends(ctx, rc, peak, faces=[rc.rx0 + 1, rc.rx1 - 2])

def _build_gable_ends(
    ctx: BuildContext,
    rc,
    peak: int,
    faces: list[int],
    accent: bool = True,
) -> None:
    """Fill the triangular gable ends with wall + accent + window blocks."""
    mat_wall   = ctx.palette.get("wall",   "minecraft:spruce_planks")
    mat_accent = ctx.palette.get("accent", "minecraft:cobblestone")
    mat_window = palette_get(ctx.palette,  "window", "minecraft:brown_stained_glass")

    if rc.pitch_along_x:
        for gz in faces:
            for layer in range(peak):
                for gx in range(rc.rx0 + layer + 1, rc.rx1 - 1 - layer):
                    ctx.place_block((gx, rc.ry + layer, gz), Block(mat_wall))
            if accent:
                for gx in range(rc.rx0 + 1, rc.rx1 - 1):
                    ctx.place_block((gx, rc.ry, gz), Block(mat_accent))
            if peak >= 3:
                if rc.rw % 2 == 0:
                    ctx.place_block((rc.mid_x - 1, rc.ry + 1, gz), Block(mat_window))
                    ctx.place_block((rc.mid_x,     rc.ry + 1, gz), Block(mat_window))
                else:
                    ctx.place_block((rc.mid_x, rc.ry + 1, gz), Block(mat_window))
    else:
        for gx in faces:
            for layer in range(peak):
                for gz in range(rc.rz0 + layer + 1, rc.rz1 - 1 - layer):
                    ctx.place_block((gx, rc.ry + layer, gz), Block(mat_wall))
            if accent:
                for gz in range(rc.rz0 + 1, rc.rz1 - 1):
                    ctx.place_block((gx, rc.ry, gz), Block(mat_accent))
            if peak >= 3:
                if rc.rd % 2 == 0:
                    ctx.place_block((gx, rc.ry + 1, rc.mid_z - 1), Block(mat_window))
                    ctx.place_block((gx, rc.ry + 1, rc.mid_z),     Block(mat_window))
                else:
                    ctx.place_block((gx, rc.ry + 1, rc.mid_z), Block(mat_window))

# ---------------------------------------------------------------------------
# Cross-gabled
# ---------------------------------------------------------------------------

def _build_cross_gabled(
    ctx: BuildContext,
    rc: _RoofCorners,
    side: str | None = None,
) -> None:
    """
    Cross-gabled roof: main gable span + one or two perpendicular dormer arms.

    side — if given, build exactly that one arm ("north","south","east","west").
           If None, randomly pick one or both valid sides.
    """
    peak = rc.span // 2
    build_gabled_roof(ctx, rc)

    if side is not None:
        _build_cross_arm(ctx, rc, peak, side)
    else:
        sides    = ["east", "west"] if rc.pitch_along_x else ["south", "north"]
        to_build = sides if random.random() < 0.6 else [random.choice(sides)]
        for s in to_build:
            _build_cross_arm(ctx, rc, peak, s)

def _cross_arm_params(rc: _RoofCorners, peak: int, side: str) -> dict:
    """Return geometry parameters for one cross-arm based on the requested side.

    Dispatch is on the cardinal direction of the arm, NOT on rc.pitch_along_x.
    The arm direction is determined by the caller (bridge_side or random choice)
    and may be perpendicular to the main ridge or parallel — both are valid
    cross-gabled shapes.  Dispatching on pitch_along_x caused wrong-axis arms
    whenever bridge_side didn't match the auto-selected main-ridge orientation.
    """
    if side in ("south", "north"):
        # Arm extends along Z (south or north). Perpendicular span is X.
        south = (side == "south")
        return dict(
            inner_start    = rc.rz1 - 1  if south else rc.rz0,
            inner_step     = -1           if south else  1,
            stair_range    = (lambda iz: range(iz + 1, rc.rz1)) if south else (lambda iz: range(rc.rz0, iz)),
            perp_a         = lambda layer: rc.mid_x - (peak - layer),
            perp_b         = lambda layer: rc.mid_x + (peak - layer),
            facing_a       = "east",
            facing_b       = "west",
            shape_a        = "inner_left"  if south else "inner_right",
            shape_b        = "inner_right" if south else "inner_left",
            make_pos_inner = lambda perp, y, inner: (perp, y, inner),
            make_pos_arm   = lambda perp, y, along: (perp, y, along),
            make_pos_ridge = lambda r, ry: (rc.mid_x, ry, r),
            ridge_range    = range(rc.mid_z + 1, rc.rz1) if south else range(rc.rz0, rc.mid_z + 1),
            gable_face     = rc.rz1 - 2  if south else rc.rz0 + 1,
            arm_rc         = _ArmRC(rc.mid_x - peak, rc.mid_x + peak + 1, rc.rz0, rc.rz0 + 2 * peak + 2, rc.ry),
        )
    else:
        # Arm extends along X (east or west). Perpendicular span is Z.
        east = (side == "east")
        return dict(
            inner_start    = rc.rx1 - 1  if east else rc.rx0,
            inner_step     = -1           if east else  1,
            stair_range    = (lambda ix: range(ix + 1, rc.rx1)) if east else (lambda ix: range(rc.rx0, ix)),
            perp_a         = lambda layer: rc.mid_z - (peak - layer),
            perp_b         = lambda layer: rc.mid_z + (peak - layer),
            facing_a       = "south",
            facing_b       = "north",
            shape_a        = "inner_left"  if east else "inner_right",
            shape_b        = "inner_right" if east else "inner_left",
            make_pos_inner = lambda perp, y, inner: (inner, y, perp),
            make_pos_arm   = lambda perp, y, along: (along, y, perp),
            make_pos_ridge = lambda r, ry: (r, ry, rc.mid_z),
            ridge_range    = range(rc.mid_x + 1, rc.rx1) if east else range(rc.rx0, rc.mid_x + 1),
            gable_face     = rc.rx1 - 2  if east else rc.rx0 + 1,
            arm_rc         = _ArmRC(rc.rx0, rc.rx0 + 2 * peak + 2, rc.mid_z - peak, rc.mid_z + peak + 1, rc.ry),
        )


def _build_cross_arm(
    ctx: BuildContext,
    rc: _RoofCorners,
    peak: int,
    side: str,
) -> None:
    mat_roof  = palette_get(ctx.palette, "roof_stairs", "minecraft:spruce_oak_stairs")
    mat_slab  = palette_get(ctx.palette, "roof_slab",   "minecraft:stone_brick_slab")

    if peak < 2:
        return

    # Arm spans the full range from ceiling (rc.ry) to the main peak.
    # Centered perp (mid_x / mid_z) never crosses, so no convergence clamp needed.
    arm_peak = peak

    if arm_peak < 2:
        return

    p = _cross_arm_params(rc, arm_peak, side)

    # Match main gable parity: odd span gets one extra layer (the ridge row);
    # even span stops at arm_peak - 1, same as build_gabled_roof's range(peak).
    arm_layers = arm_peak + (1 if rc.span % 2 == 1 else 0)
    for layer in range(arm_layers):
        arm_y  = rc.ry + layer
        inner  = p["inner_start"] + p["inner_step"] * layer
        perp_a = p["perp_a"](layer)
        perp_b = p["perp_b"](layer)

        ctx.place_block(
            p["make_pos_inner"](perp_a, arm_y, inner),
            Block(mat_roof, {"facing": p["facing_a"], "shape": p["shape_a"]}),
        )
        ctx.place_block(
            p["make_pos_inner"](perp_b, arm_y, inner),
            Block(mat_roof, {"facing": p["facing_b"], "shape": p["shape_b"]}),
        )
        for along in p["stair_range"](inner):
            ctx.place_block(
                p["make_pos_arm"](perp_a, arm_y, along),
                Block(mat_roof, {"facing": p["facing_a"]}),
            )
            ctx.place_block(
                p["make_pos_arm"](perp_b, arm_y, along),
                Block(mat_roof, {"facing": p["facing_b"]}),
            )

    if rc.span % 2 == 1:
        ridge_y = rc.ry + arm_peak
        for r in p["ridge_range"]:
            ctx.place_block(
                p["make_pos_ridge"](r, ridge_y),
                Block(mat_slab, {"type": "bottom"}),
            )
    _build_gable_ends(ctx, p["arm_rc"], arm_peak, faces=[p["gable_face"]], accent=False)