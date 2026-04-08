"""
structures/misc/tavern.py
--------------------------
Medieval tavern complex: stone tower + arched bridge + cottage.

Three-part layout along the primary axis:
  [ Tower (tw) ] [ Bridge (bw) ] [ Cottage (cw) ]

The bridge connects the tower to the cottage along the primary axis.
Two parallel belfry-style arches (the same arch used in the tower) run
along the bridge walls; fence pillars above support a gabled roof.
Bridge width matches the tower width (tw).

The cottage door faces PERPENDICULAR to the bridge so the entrance is
on the long side of the cottage, never toward the bridge.

Rotation is fully supported via BuildContext:
  rotation=0   → structure runs along +X
  rotation=90  → structure runs along +Z
  rotation=180 → runs along -X
  rotation=270 → runs along -Z

Minimum plot: 19 wide × 8 deep.
"""
from __future__ import annotations

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from world_interface.block_buffer import BlockBuffer
from structures.base.primitives import (
    add_chimney,
    add_door,
    add_lanterns,
    add_windows,
    build_belfry_face,
    build_ceiling,
    build_floor,
    build_foundation,
    build_walls,
)
from structures.roofs.roof_builder import _RoofCorners, build_gabled_roof, build_roof
from structures.tower.tower_builder import TowerBuilder


class _BridgeRC(_RoofCorners):
    """
    _RoofCorners with pitch axis locked to the bridge span direction.

    The standard _RoofCorners auto-selects pitch based on which dimension
    is shorter.  For a bridge the ridge must always run along the span
    (the bridge length), regardless of the width/length ratio.
    """

    def __init__(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        pitch_along_x: bool,
    ) -> None:
        super().__init__(x, y, z, w, d)
        self._pitch = pitch_along_x

    @property
    def pitch_along_x(self) -> bool:   # type: ignore[override]
        return self._pitch

    @property
    def span(self) -> int:
        return self.rw if self._pitch else self.rd

    @property
    def length(self) -> int:
        return self.rd if self._pitch else self.rw


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FOUND_DEPTH: int = 1       # column depth below plot.y to reach uneven ground

_MIN_TW: int = 5            # tower footprint (square)
_MIN_BW: int = 7            # bridge length along primary axis
_MIN_CW: int = 7            # cottage width along primary axis
_MIN_W:  int = _MIN_TW + _MIN_BW + _MIN_CW   # = 19

_MIN_D:  int = 8            # shared depth (perpendicular to primary axis)

_BRIDGE_HEIGHT: int = 3     # bridge floor height above plot.y


# ---------------------------------------------------------------------------
# Bridge helper
# ---------------------------------------------------------------------------

def _build_bridge(
    palette: PaletteSystem,
    x: int, y: int, z: int,
    bridge_len: int,
    bridge_w: int,
    bridge_y: int,
    span_axis: str,
) -> BlockBuffer:
    """
    Arched bridge using the same belfry-face arch as the tower.

    span_axis='x': bridge runs along X (bridge_len blocks), width=bridge_w along Z.
    span_axis='z': bridge runs along Z (bridge_len blocks), width=bridge_w along X.

    Builds all bridge elements — arches, floor, fences, ceiling, roof — into
    its own BlockBuffer and returns it complete, ready to be merged last.
    """
    buf = BlockBuffer()

    stone_id  = palette_get(palette, "foundation", "minecraft:stone_bricks")
    log_mat   = palette_get(palette, "accent",     "minecraft:dark_oak_log")
    plank_mat = palette_get(palette, "wall",       "minecraft:dark_oak_planks")
    stair_mat = palette_get(palette, "roof",       "minecraft:dark_oak_stairs")
    fence_id  = palette_get(palette, "fence",      "minecraft:spruce_fence")
    plank_id  = palette_get(palette, "floor",      "minecraft:spruce_planks")
    trap_mat  = "minecraft:dark_oak_trapdoor"

    lintel_y    = bridge_y
    arch_y      = bridge_y - 1
    fence_top_y = bridge_y + 4

    # End arch (doorway opening): lintel sits 3 blocks above the bridge floor
    door_lintel_y = bridge_y + 4
    door_arch_y   = bridge_y + 3

    # BuildContext for build_belfry_face (rotation=0, world coords pass through)
    ctx = BuildContext(buf, dict(palette), rotation=0,
                       origin=(x, y, z), size=(bridge_len, bridge_w))

    def _arch_face(fixed_coord: int, span_start: int, span_end: int,
                   make_pos,        # (span_i, fixed) → (x, z)
                   stair_left: dict, stair_right: dict) -> None:
        """Place one arch face: corner log pillars + belfry-face arch detail."""
        # Corner dark-oak log columns only — interior is open
        for corner in [span_start, span_end]:
            cx, cz = make_pos(corner, fixed_coord)
            for dy in range(1, _FOUND_DEPTH + 1):
                buf.place(cx, y - dy, cz, Block(stone_id))
            for by in range(y, lintel_y + 1):
                buf.place(cx, by, cz, Block(log_mat))

        # Belfry-face arch (plank lintel + stair shoulders + trapdoor keystone)
        build_belfry_face(
            ctx,
            lintel_y=lintel_y,
            arch_y=arch_y,
            along=[make_pos(si, fixed_coord) for si in range(span_start + 1, span_end)],
            plank_mat=plank_mat,
            stair_mat=stair_mat,
            trap_mat=trap_mat,
            stair_left=stair_left,
            stair_right=stair_right,
        )

    if span_axis == 'x':
        z_left  = z
        z_right = z + bridge_w - 1

        _arch_face(z_left,  x, x + bridge_len - 1,
                   make_pos=lambda si, fz: (si, fz),
                   stair_left={"facing": "west", "half": "top"},
                   stair_right={"facing": "east", "half": "top"})
        _arch_face(z_right, x, x + bridge_len - 1,
                   make_pos=lambda si, fz: (si, fz),
                   stair_left={"facing": "west", "half": "top"},
                   stair_right={"facing": "east", "half": "top"})

        # End arches — doorway portals at each bridge entry/exit
        for end_x in [x - 1, x + bridge_len]:
            build_belfry_face(
                ctx,
                lintel_y=door_lintel_y,
                arch_y=door_arch_y,
                along=[(end_x, bz) for bz in range(z_left + 1, z_right)],
                plank_mat=plank_mat,
                stair_mat=stair_mat,
                trap_mat=trap_mat,
                stair_left={"facing": "north", "half": "top"},
                stair_right={"facing": "south", "half": "top"},
            )

        # Bridge floor
        for bx in range(x, x + bridge_len):
            for bz in range(z_left, z_right + 1):
                buf.place(bx, bridge_y, bz, Block(plank_id))
            for bz in [z_left, z_right]:
                for fy in range(bridge_y + 1, fence_top_y + 1):
                    buf.place(bx, fy, bz, Block(fence_id))
            for bz in range(z_left, z_right + 1):
                buf.place(bx, fence_top_y, bz, Block(plank_id))

        ctx_r  = BuildContext(buf, dict(palette), rotation=0,
                              origin=(x + 1, fence_top_y + 1, z), size=(bridge_len - 1, bridge_w))
        rc_bri = _BridgeRC(x + 1, fence_top_y + 1, z, bridge_len - 2, bridge_w, pitch_along_x=False)
        build_gabled_roof(ctx_r, rc_bri)

    else:  # span_axis == 'z'
        x_left  = x
        x_right = x + bridge_w - 1

        _arch_face(x_left,  z, z + bridge_len - 1,
                   make_pos=lambda si, fx: (fx, si),
                   stair_left={"facing": "north", "half": "top"},
                   stair_right={"facing": "south", "half": "top"})
        _arch_face(x_right, z, z + bridge_len - 1,
                   make_pos=lambda si, fx: (fx, si),
                   stair_left={"facing": "north", "half": "top"},
                   stair_right={"facing": "south", "half": "top"})

        # End arches — doorway portals at each bridge entry/exit
        for end_z in [z - 1, z + bridge_len]:
            build_belfry_face(
                ctx,
                lintel_y=door_lintel_y,
                arch_y=door_arch_y,
                along=[(bx, end_z) for bx in range(x_left + 1, x_right)],
                plank_mat=plank_mat,
                stair_mat=stair_mat,
                trap_mat=trap_mat,
                stair_left={"facing": "west", "half": "top"},
                stair_right={"facing": "east", "half": "top"},
            )

        # Bridge floor
        for bz in range(z, z + bridge_len):
            for bx in range(x_left, x_right + 1):
                buf.place(bx, bridge_y, bz, Block(plank_id))
            for bx in [x_left, x_right]:
                for fy in range(bridge_y + 1, fence_top_y + 1):
                    buf.place(bx, fy, bz, Block(fence_id))
            for bx in range(x_left, x_right + 1):
                buf.place(bx, fence_top_y, bz, Block(plank_id))

        ctx_r  = BuildContext(buf, dict(palette), rotation=0,
                              origin=(x, fence_top_y + 1, z + 1), size=(bridge_w, bridge_len - 1))
        rc_bri = _BridgeRC(x, fence_top_y + 1, z + 1, bridge_w, bridge_len - 1, pitch_along_x=True)
        build_gabled_roof(ctx_r, rc_bri)


    return buf


# ---------------------------------------------------------------------------
# Annex helper
# ---------------------------------------------------------------------------

def _build_annex(
    buffer: BlockBuffer,
    palette: PaletteSystem,
    x: int, y: int, z: int,
    cw: int, d: int,
    wall_h: int,
    bridge_side: str,
    rotation: int,
) -> None:
    """
    Half-timbered annex (habitation wing).  Door faces perpendicular to the
    bridge so the entrance is on the long side, never toward the bridge.

    bridge_side west/east → bridge axis is X → door on south face
    bridge_side north/south → bridge axis is Z → door on east face
    """
    ctx = BuildContext(buffer, palette, rotation=rotation,
                       origin=(x, y, z), size=(cw, d))

    door_facing = "south" if bridge_side in ("west", "east") else "east"
    accent = palette_get(palette, "accent", "minecraft:spruce_log")

    with ctx.push():
        build_foundation(ctx, x, y, z, cw, d)
        build_floor(ctx,      x, y, z, cw, d)
        build_walls(ctx,      x, y, z, cw, wall_h, d)

        # Half-timbered frame posts start at y (ground level), not y+1
        for dy in range(0, wall_h):
            for dx in range(0, cw, max(2, cw // 3)):
                ctx.place_block((x + dx, y + dy, z),         Block(accent))
                ctx.place_block((x + dx, y + dy, z + d - 1), Block(accent))
            for dz in range(0, d, max(2, d // 3)):
                ctx.place_block((x,          y + dy, z + dz), Block(accent))
                ctx.place_block((x + cw - 1, y + dy, z + dz), Block(accent))

        add_door(ctx, x, y, z, cw, facing=door_facing)
        add_windows(ctx, x, y, z, cw, d)
        build_ceiling(ctx, x, y + wall_h, z, cw, d, floor_y=y)
        roof_y = y + wall_h + 1
        build_roof(ctx, x, roof_y, z, cw, d, "cross", bridge_side)
        add_lanterns(ctx,  x, y, z, cw, d)
        add_chimney(ctx,   x, y, z, cw, d, wall_h + 4)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bridge_side(rotation: int) -> str:
    """
    Return the cardinal face of the annex that the bridge connects to.

    rotation=0   → bridge runs +X → hits annex west face  → "west"
    rotation=90  → bridge runs +Z → hits annex north face → "north"
    rotation=180 → bridge runs -X → hits annex east face  → "east"
    rotation=270 → bridge runs -Z → hits annex south face → "south"
    """
    return ("west", "north", "east", "south")[(rotation // 90) % 4]


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class Tavern:
    """
    Three-part medieval complex: stone tower → arched bridge → half-timbered annex.

    Layout (rotation=0, along X):
      x ────────────────────────────────────────────────────── x+w
      [ Tower (tw×tw) ][ Bridge (bw×tw) ][ Annex (cw×d) ]

    Bridge width matches the tower (tw), not the plot depth.
    Bridge arches use the same belfry-face arch as the tower.

    rotation=0/180 → primary axis along X
    rotation=90/270 → primary axis along Z
    """

    def build(
        self,
        plot: Plot,
        palette: PaletteSystem,
        rotation: int = 0,
        with_tower: bool = True,
        with_bridge: bool = True,
    ) -> BlockBuffer:
        x, y, z = plot.x, plot.y, plot.z
        w, d    = plot.width, plot.depth
        buffer  = BlockBuffer()

        if w < _MIN_W or d < _MIN_D:
            return buffer

        tw = _MIN_TW   # fixed tower width — don't grow with depth or bridge breaks
        bw = max(_MIN_BW, int(w * 0.25))
        cw = w - tw - bw
        if cw < _MIN_CW:
            bw = max(_MIN_BW, w - tw - _MIN_CW)
            cw = w - tw - bw
        if cw < _MIN_CW:
            return buffer

        wall_h   = max(5, min(d - 2, 7))
        bridge_y = y + _BRIDGE_HEIGHT

        # Tower stone-base height so the belfry starts at the bridge roof peak.
        # TowerBuilder: belfry_y = y + tower_h + 2
        # Bridge roof peak = y + _BRIDGE_HEIGHT + 4 + (tw + 2) // 2
        #   (_BRIDGE_HEIGHT+3 = fence_top_y offset, +1 roof start, +(tw+2)//2 peak)
        tower_h = _BRIDGE_HEIGHT + 3 + (tw + 2) // 2

        steps     = (rotation // 90) % 4
        span_axis = 'z' if steps in (1, 3) else 'x'

        if span_axis == 'x':
            t_offset_z = (d - tw) // 2
            if with_tower:
                tower_buf = TowerBuilder(
                    palette,
                    height=tower_h, width=tw,
                    with_door=True, with_windows=True,
                    rotation=rotation,
                ).build_at(x, y, z + t_offset_z)
                buffer.merge(tower_buf)

            if with_bridge:
                bridge_buf = _build_bridge(palette,
                                           x + tw, y, z + t_offset_z,
                                           bridge_len=bw, bridge_w=tw,
                                           bridge_y=bridge_y, span_axis='x')

            _build_annex(buffer, palette,
                         x + tw + bw, y, z, cw, d, wall_h,
                         bridge_side=_bridge_side(rotation), rotation=rotation)

        else:  # span_axis == 'z'
            t_offset_x = (d - tw) // 2
            if with_tower:
                tower_buf = TowerBuilder(
                    palette,
                    height=tower_h, width=tw,
                    with_door=True, with_windows=True,
                    rotation=rotation,
                ).build_at(x + t_offset_x, y, z)
                buffer.merge(tower_buf)

            if with_bridge:
                bridge_buf = _build_bridge(palette,
                                           x + t_offset_x, y, z + tw,
                                           bridge_len=bw, bridge_w=tw,
                                           bridge_y=bridge_y, span_axis='z')

            _build_annex(buffer, palette,
                         x, y, z + tw + bw, d, cw, wall_h,
                         bridge_side=_bridge_side(rotation), rotation=rotation)

        # Bridge (with its roof) merged last so nothing overwrites it
        if with_bridge:
            buffer.merge(bridge_buf)

        return buffer
