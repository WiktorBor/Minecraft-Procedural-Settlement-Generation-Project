"""
structures/house/house_context.py
----------------------------------
Build context (parameter bundle) for the house shape grammar.

Pure data — no GDPC or builder dependencies beyond the type annotation.

Changes from original
---------------------
  • `editor` is now a required constructor argument, injected at build time
    by HouseGrammar._place().  It is no longer an Any field that defaults to
    None and is set after the fact — that pattern hid missing-editor bugs
    until the first placeBlock call.

  • Derived properties (base_y, wall_top_y, ceiling_y, etc.) are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette


@dataclass
class Ctx:
    """
    All coordinates, dimensions, and feature flags for a single house build.

    Created by HouseGrammar._make_context() and passed to every sub-builder.
    The editor is supplied at construction time — there is no post-hoc setter.
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
    roof_type: str       # "pyramid" | "gabled" | "cross"

    # Optional features
    has_chimney: bool
    has_porch:   bool

    # Door orientation: 0 → z_min face (north-facing door), 1 → z_max face (south-facing door)
    door_face: int

    # Materials
    palette: BiomePalette

    # Editor — required; supplied by HouseGrammar._place() at build time.
    editor: Editor

    # Clockwise rotation in degrees — 0, 90, 180, 270.
    # Applied via editor.pushTransform in HouseGrammar._place().
    # Must be last so the default doesn't break Python 3.9 dataclass field ordering.
    rotation: int = 0

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