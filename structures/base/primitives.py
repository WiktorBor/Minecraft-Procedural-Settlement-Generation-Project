"""
structures/base/primitives.py
------------------------------
Palette-aware primitive building functions shared by ALL structure builders.

Every function takes a BuildContext as its first argument.  None of them
know about rotation — that is handled by BuildContext.push().  Callers
pass world-absolute coordinates; the active transform (if any) rotates them.

Primitive functions
-------------------
  build_foundation  — solid block(s) driven into the ground (perimeter or solid)
  build_floor       — solid rectangle at a fixed Y
  build_flat_roof   — solid rectangle at a fixed Y using the roof palette key
  build_walls       — hollow box from y+1 to y+height
  add_door          — two-block door centred on a face, using palette door block
  add_windows       — windows on faces wide/deep enough to fit them
  add_chimney       — single-column chimney at back-right corner
  add_lanterns      — corner lanterns at base level
  build_belfry      — open belfry with arched openings on all four faces
  build_belfry_face — single arched face (plank lintel + stair/trapdoor arch)
  build_log_belt    — perimeter ring of accent logs at a single Y level

All block IDs come from ctx.palette so the same function works in any biome.
"""
from __future__ import annotations

from gdpc import Block

from data.biome_palettes import palette_get
from structures.base.build_context import BuildContext


# ---------------------------------------------------------------------------
# Foundations and floors
# ---------------------------------------------------------------------------

def build_foundation(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    depth_below: int = 1,
) -> None:
    """
    Solid foundation block column driven downward from y, using the
    'foundation' palette key.

    Embeds the structure into uneven terrain naturally by filling the
    `depth_below` layers below the surface.

    Args:
        ctx:         Build context.
        x, y, z:     Top-left anchor at surface level.
        width, depth: Footprint dimensions.
        depth_below: How many blocks below y to fill (default 3).
    """
    positions = [
        (x + dx, y - dy, z + dz)
        for dx in range(width)
        for dz in range(depth)
        for dy in range(1, depth_below + 1)
    ]
    ctx.place_many(positions, "foundation")


def build_floor(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
) -> None:
    """
    Solid floor rectangle at y using the 'floor' palette key.

    Args:
        ctx:          Build context.
        x, y, z:      Top-left anchor.
        width, depth: Rectangle dimensions.
    """
    positions = [
        (x + dx, y, z + dz)
        for dx in range(width)
        for dz in range(depth)
    ]
    ctx.place_many(positions, "floor")


def build_flat_roof(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
) -> None:
    """
    Flat roof rectangle at y using the 'roof' palette key.

    Args:
        ctx:          Build context.
        x, y, z:      Top-left anchor.
        width, depth: Rectangle dimensions.
    """
    positions = [
        (x + dx, y, z + dz)
        for dx in range(width)
        for dz in range(depth)
    ]
    ctx.place_many(positions, "roof")


# ---------------------------------------------------------------------------
# Walls
# ---------------------------------------------------------------------------

def build_walls(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, height: int, depth: int,
) -> None:
    """
    Hollow walls from y+1 to y+height (exclusive) using the 'wall' palette key.

    The floor at y is assumed to already exist.  Corner blocks are placed
    exactly once — no duplicate placements at intersections.

    Args:
        ctx:                Build context.
        x, y, z:            Bottom-left anchor (floor level).
        width, height, depth: Wall dimensions.
    """
    positions = []
    for dy in range(1, height):
        # Z-facing walls (south + north)
        for dx in range(width):
            positions.append((x + dx,         y + dy, z))
            positions.append((x + dx,         y + dy, z + depth - 1))
        # X-facing walls (east + west), skip corners already covered above
        for dz in range(1, depth - 1):
            positions.append((x,              y + dy, z + dz))
            positions.append((x + width - 1,  y + dy, z + dz))
    ctx.place_many(positions, "wall")


# ---------------------------------------------------------------------------
# Doors and windows
# ---------------------------------------------------------------------------

def add_door(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int,
    facing: str = "south",
) -> None:
    """
    Place a two-block-tall door at the centre of the south face (z).

    Uses the 'door' palette key.  Places a floor block beneath the door
    (using the 'floor' palette key) so there is always a solid step.

    Args:
        ctx:    Build context.
        x, y, z: Bottom-left anchor of the wall face.
        width:  Wall width — door is centred at x + width // 2.
        facing: Minecraft facing direction for the door (default 'south').
    """
    door_x    = x + width // 2
    door_id   = palette_get(ctx.palette, "door", "minecraft:spruce_door")

    ctx.place((door_x, y, z), "floor")
    ctx.place_block(
        (door_x, y + 1, z),
        Block(door_id, {"facing": facing, "half": "lower", "hinge": "left"}),
    )
    ctx.place_block(
        (door_x, y + 2, z),
        Block(door_id, {"facing": facing, "half": "upper", "hinge": "left"}),
    )


def add_windows(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    window_y_offset: int = 2,
) -> None:
    """
    Place windows on faces that are wide enough (> 5 blocks) using the
    'window' palette key.

    Places two windows per long face (near each corner) and one window
    per short face (at mid-depth).

    Args:
        ctx:              Build context.
        x, y, z:          Bottom-left anchor.
        width, depth:     Footprint dimensions.
        window_y_offset:  Y offset above y where windows are placed (default 2).
    """
    wy        = y + window_y_offset
    positions = []

    if width > 5:
        positions += [
            (x + 1,         wy, z),
            (x + width - 2, wy, z),
            (x + 1,         wy, z + depth - 1),
            (x + width - 2, wy, z + depth - 1),
        ]
    if depth > 5:
        positions += [
            (x,             wy, z + depth // 2),
            (x + width - 1, wy, z + depth // 2),
        ]

    if positions:
        ctx.place_many(positions, "window")


# ---------------------------------------------------------------------------
# Chimney and lanterns
# ---------------------------------------------------------------------------

def add_chimney(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    building_height: int,
) -> None:
    """
    Single-column chimney at the back-right corner of the structure,
    using the 'foundation' palette key (stone/cobblestone material).

    The chimney rises from y to y + building_height.

    Args:
        ctx:              Build context.
        x, y, z:          Bottom-left anchor of the building.
        width, depth:     Building footprint.
        building_height:  How many blocks tall the chimney column should be.
    """
    chimney_x = x + width - 2
    chimney_z = z + depth - 2
    positions = [(chimney_x, y + dy, chimney_z) for dy in range(building_height)]
    ctx.place_many(positions, "foundation")


def build_ceiling(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    deco_x: int | None = None,
    deco_z: int | None = None,
    floor_y: int | None = None,
) -> None:
    """
    Beam ring (accent_beam) around the perimeter, slab fill (ceiling_slab)
    in the interior, and a light source at the centre.

    Light placement rules:
      >= 9x9 : interior_light flush at ceiling level (y).
      <= 4 wide or deep : hay bale at y-2 + lantern at y-1.
      otherwise : interior_light hanging at y-1.

    deco_x / deco_z override the default centre position for the decoration,
    so callers can place it opposite a door or at any specific spot.

    Args:
        ctx:           Build context.
        x, y, z:       Top-left anchor at ceiling level.
        width, depth:  Footprint dimensions.
        deco_x, deco_z: Override decoration X/Z (defaults to footprint centre).
    """
    mat_beam    = palette_get(ctx.palette, "accent_beam",    "minecraft:stripped_spruce_log")
    mat_ceiling = palette_get(ctx.palette, "ceiling_slab",   "minecraft:oak_slab")
    mat_light   = palette_get(ctx.palette, "interior_light", "minecraft:pearlescent_froglight")

    beam_pos  = []
    ceil_pos  = []
    for dx in range(width):
        for dz in range(depth):
            pos     = (x + dx, y, z + dz)
            on_edge = dx == 0 or dx == width - 1 or dz == 0 or dz == depth - 1
            (beam_pos if on_edge else ceil_pos).append(pos)

    beam_blk = Block(mat_beam)
    ceil_blk = Block(mat_ceiling, {"type": "top"})
    for pos in beam_pos:
        ctx.place_block(pos, beam_blk)
    for pos in ceil_pos:
        ctx.place_block(pos, ceil_blk)

    cx = deco_x if deco_x is not None else x + width  // 2
    cz = deco_z if deco_z is not None else z + depth  // 2

    if width >= 9 and depth >= 9:
        # Large ceiling: flush light embedded at ceiling level (one block higher)
        ctx.place_block((cx, y, cz), Block(mat_light))
    elif width <= 4 or depth <= 4:
        # Small ceiling: hay bale on the floor with a lantern on top
        hay_y = (floor_y + 1) if floor_y is not None else (y - 2)
        ctx.place_block((cx, hay_y,     cz), Block("minecraft:hay_block", {"axis": "y"}))
        ctx.place_block((cx, hay_y + 1, cz), Block("minecraft:lantern",   {"hanging": "false"}))
    else:
        # Default: interior light flush at ceiling level
        ctx.place_block((cx, y, cz), Block(mat_light))


def add_lanterns(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
) -> None:
    """
    Place lanterns at the four base corners of the structure using the
    'light' palette key.

    The hanging state is applied automatically if the block supports it
    (via BuildContext.place_light).

    Args:
        ctx:          Build context.
        x, y, z:      Bottom-left anchor.
        width, depth: Building footprint.
    """
    corners = [
        (x,             y, z),
        (x + width - 1, y, z),
        (x,             y, z + depth - 1),
        (x + width - 1, y, z + depth - 1),
    ]
    for pos in corners:
        ctx.place_light(pos, key="light", hanging=False)


# ---------------------------------------------------------------------------
# Log belt
# ---------------------------------------------------------------------------

def build_log_belt(
    ctx: BuildContext,
    x: int, y: int, z: int,
    w: int, d: int,
) -> None:
    """
    Perimeter ring of accent logs at a single Y level.

    Used as a transition band between a stone base and an upper belfry section.

    Args:
        ctx:     Build context (palette + editor).
        x, y, z: Anchor corner of the footprint.
        w, d:    Width and depth of the footprint.
    """
    log_mat = palette_get(ctx.palette, "accent", "minecraft:dark_oak_log")
    for dx in range(w):
        for dz in range(d):
            if dx == 0 or dx == w - 1 or dz == 0 or dz == d - 1:
                ctx.place_block((x + dx, y, z + dz), Block(log_mat))


# ---------------------------------------------------------------------------
# Belfry arch
# ---------------------------------------------------------------------------

def build_belfry(
    ctx: BuildContext,
    x: int, y: int, z: int,
    w: int, d: int,
    h: int = 4,
) -> None:
    """
    Open belfry section with arched openings on all four faces.

    Each face has:
      - Corner dark-oak log columns (full height h)
      - Plank lintel across the top of the opening
      - Stair arch one row below (pair of upside-down inward-facing stairs
        with a trapdoor keystone in the centre)
      - Fully open interior below the arch

    Args:
        ctx:     Build context (palette + editor).
        x, y, z: Anchor corner of the belfry footprint.
        w, d:    Width and depth of the footprint.
        h:       Height of the belfry section (default 4).
    """
    log_mat   = palette_get(ctx.palette, "accent",    "minecraft:dark_oak_log")
    plank_mat = palette_get(ctx.palette, "wall",      "minecraft:dark_oak_planks")
    stair_mat = ctx.palette.get("roof",               "minecraft:dark_oak_stairs")
    trap_mat  = "minecraft:dark_oak_trapdoor"

    lintel_y = y + h - 1   # top row  : planks
    arch_y   = y + h - 2   # row below: stair + trapdoor + stair

    # Corner log columns (full height)
    for dy in range(h):
        for cx, cz in [(x, z), (x+w-1, z), (x, z+d-1), (x+w-1, z+d-1)]:
            ctx.place_block((cx, y + dy, cz), Block(log_mat))

    # South face (vary X, fixed Z = z)
    build_belfry_face(ctx, lintel_y, arch_y,
                 along=[(x + dx, z) for dx in range(1, w - 1)],
                 plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                 stair_left ={"facing": "west",  "half": "top"},
                 stair_right={"facing": "east",  "half": "top"})

    # North face (vary X, fixed Z = z+d-1)
    build_belfry_face(ctx, lintel_y, arch_y,
                 along=[(x + dx, z + d - 1) for dx in range(1, w - 1)],
                 plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                 stair_left ={"facing": "west",  "half": "top"},
                 stair_right={"facing": "east",  "half": "top"})

    # West face (vary Z, fixed X = x)
    build_belfry_face(ctx, lintel_y, arch_y,
                 along=[(x, z + dz) for dz in range(1, d - 1)],
                 plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                 stair_left ={"facing": "north", "half": "top"},
                 stair_right={"facing": "south", "half": "top"})

    # East face (vary Z, fixed X = x+w-1)
    build_belfry_face(ctx, lintel_y, arch_y,
                 along=[(x + w - 1, z + dz) for dz in range(1, d - 1)],
                 plank_mat=plank_mat, stair_mat=stair_mat, trap_mat=trap_mat,
                 stair_left ={"facing": "north", "half": "top"},
                 stair_right={"facing": "south", "half": "top"})


def build_belfry_face(
    ctx: BuildContext,
    lintel_y: int,
    arch_y: int,
    along: list[tuple[int, int]],
    plank_mat: str,
    stair_mat: str,
    trap_mat: str,
    stair_left: dict,
    stair_right: dict,
) -> None:
    """
    Place one arched face: plank lintel row + 3-wide stair arch below it.

    lintel_y  — top row: planks spanning the full inner width
    arch_y    — row below: left stair | trapdoor | right stair (centred)
    along     — ordered (x, z) positions of the arch span (min 3)
    """
    n = len(along)
    if n < 3:
        return

    mid      = n // 2
    left_i   = mid - 1
    center_i = mid
    right_i  = mid + 1

    for i, (px, pz) in enumerate(along):
        ctx.place_block((px, lintel_y, pz), Block(plank_mat))

        if i == left_i:
            ctx.place_block((px, arch_y, pz), Block(stair_mat, stair_left))
        elif i == center_i:
            ctx.place_block((px, arch_y, pz),
                            Block(trap_mat, {"facing": "south", "open": "false", "half": "top"}))
        elif i == right_i:
            ctx.place_block((px, arch_y, pz), Block(stair_mat, stair_right))
        else:
            ctx.place_block((px, arch_y, pz), Block(plank_mat))