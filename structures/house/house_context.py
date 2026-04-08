"""
structures/house/house_context.py
----------------------------------
Build context (parameter bundle) for the house shape grammar.

Pure data — no GDPC or builder dependencies beyond the type annotation.
All block placements accumulate into a BlockBuffer; nothing touches the world directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from world_interface.block_buffer import BlockBuffer


@dataclass
class Ctx:
    """
    All coordinates, dimensions, and feature flags for a single house build.

    Created by HouseGrammar._make_context() and passed to every sub-builder.
    The buffer is the write target — builders call ctx.place_block() or
    ctx.place_many() to accumulate blocks without touching the world directly.
    """

    # World anchor
    x: int
    y: int
    z: int

    # Footprint (outer wall dimensions)
    w: int   # width  (reference = 7, always odd)
    d: int   # depth  (reference = 7, always odd)

    # Lower storey
    wall_h: int          # wall layers above the foundation level (reference = 3)

    # Upper storey (half-timbered box above the ceiling ring)
    has_upper: bool
    upper_h:   int       # height in blocks (0 when has_upper is False)

    # Roof
    roof_type:  str            # "pyramid" | "gabled" | "cross"
    cross_side: str | None     # force a specific arm side for "cross" roofs: "north"|"south"|"east"|"west"

    # Optional features
    has_chimney: bool
    has_porch:   bool

    # Door orientation: 0 → z_min face (north-facing door), 1 → z_max face (south-facing door)
    door_face: int

    # Materials
    palette: PaletteSystem

    # Write target — all block placements go here.
    buffer: BlockBuffer = field(default_factory=BlockBuffer)

    # Clockwise rotation in degrees — 0, 90, 180, 270.
    # Applied by HouseGrammar after building via coordinate transform on the buffer.
    # Must be last so the default doesn't break Python 3.9 dataclass field ordering.
    rotation: int = 0

    # ------------------------------------------------------------------
    # Block placement helpers (BuildContext-compatible interface)
    # ------------------------------------------------------------------

    def place_block(self, pos, block: Block) -> None:
        """Place a single block. pos is (x, y, z)."""
        self.buffer.place(int(pos[0]), int(pos[1]), int(pos[2]), block)

    def place_many(self, positions, key: str, states: dict | None = None) -> None:
        """Place a palette-keyed block at every position in the list."""
        mat   = palette_get(self.palette, key, "minecraft:stone")
        blk   = Block(mat, states) if states else Block(mat)
        self.buffer.place_many(positions, blk)

    # ------------------------------------------------------------------
    # Derived Y levels
    # ------------------------------------------------------------------

    @property
    def base_y(self) -> int:
        """Surface level — floor of the lower storey."""
        return self.y

    @property
    def wall_top_y(self) -> int:
        """Top beam row of the lower storey walls."""
        return self.y + self.wall_h

    @property
    def ceiling_y(self) -> int:
        """Beam ring + slab ceiling sitting above the lower storey walls."""
        return self.wall_top_y + 1

    @property
    def upper_top_y(self) -> int:
        """Top of the upper storey walls (valid only when has_upper is True)."""
        return self.ceiling_y + self.upper_h

    @property
    def roof_base_y(self) -> int:
        """Y where the roof starts — one above upper storey (or ceiling)."""
        if self.has_upper:
            return self.upper_top_y + 1
        return self.ceiling_y + 1

    # ------------------------------------------------------------------
    # Derived XZ helpers
    # ------------------------------------------------------------------

    @property
    def door_z(self) -> int:
        """Z coordinate of the door face."""
        return self.z if self.door_face == 0 else self.z + self.d - 1

    @property
    def back_z(self) -> int:
        """Z coordinate of the face opposite the door."""
        return self.z + self.d - 1 if self.door_face == 0 else self.z

    @property
    def door_facing(self) -> str:
        """
        Minecraft 'facing' value for the door block in local (pre-rotation) space.
        Always north or south — GDPC's pushTransform rotates the block state
        to the correct world direction when rotation != 0.
        """
        return "north" if self.door_face == 0 else "south"

    @property
    def door_x(self) -> int:
        """X coordinate of the door centre column."""
        return self.x + self.w // 2

    @property
    def mid_x(self) -> int:
        return self.x + self.w // 2

    @property
    def mid_z(self) -> int:
        return self.z + self.d // 2