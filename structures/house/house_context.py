"""
Build context for the house shape grammar.

Pure data — no GDPC or builder dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from data.biome_palettes import BiomePalette


@dataclass
class Ctx:
    """All coordinates and dimensions for a single house build."""

    x: int
    y: int
    z: int

    w: int   # outer wall footprint width  (reference = 7)
    d: int   # outer wall footprint depth  (reference = 7)

    # lower storey
    wall_h: int          # wall layers above foundation (reference = 3)

    # upper storey (half-timbered box above the ceiling)
    has_upper:    bool
    upper_h:      int    # upper storey wall height in blocks (reference = 3)

    # roof
    roof_type:    str    # "pyramid" | "gabled" | "cross"

    # optional features
    has_chimney:  bool
    has_porch:    bool

    # door face:  0 → z_min face,  1 → z_max face
    door_face:    int

    palette: BiomePalette

    # Editor — set by HouseGrammar._place() before any builder is called.
    # Any to avoid importing gdpc here (pure-data module).
    editor: Any = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Derived Y levels
    # ------------------------------------------------------------------

    @property
    def base_y(self) -> int:
        return self.y

    @property
    def wall_top_y(self) -> int:
        """Top beam row of the lower storey."""
        return self.y + self.wall_h

    @property
    def ceiling_y(self) -> int:
        """Beam ring + slab ceiling above the lower walls."""
        return self.wall_top_y + 1

    @property
    def upper_top_y(self) -> int:
        """Top of the upper storey walls (only valid when has_upper)."""
        return self.ceiling_y + self.upper_h

    @property
    def roof_base_y(self) -> int:
        """Y where the roof starts (one above the upper storey or ceiling)."""
        if self.has_upper:
            return self.upper_top_y + 1
        return self.ceiling_y + 1

    # ------------------------------------------------------------------
    # Derived XZ helpers
    # ------------------------------------------------------------------

    @property
    def door_z(self) -> int:
        return self.z if self.door_face == 0 else self.z + self.d - 1

    @property
    def back_z(self) -> int:
        return self.z + self.d - 1 if self.door_face == 0 else self.z

    @property
    def door_facing(self) -> str:
        return "north" if self.door_face == 0 else "south"

    @property
    def door_x(self) -> int:
        return self.x + self.w // 2

    @property
    def mid_x(self) -> int:
        return self.x + self.w // 2

    @property
    def mid_z(self) -> int:
        return self.z + self.d // 2