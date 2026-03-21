"""
Build context for the house shape grammar.

Pure data — no GDPC or builder dependencies.

Reference house (small_house.nbt) anatomy
------------------------------------------
  Wall footprint : 7 x 7
  Foundation     : Y=0  cobblestone perimeter ring
  Floor          : Y=0  oak_planks interior (with occasional moss_block)
  Lower walls    : Y=1–3  (wall_h = 3)
                   - corner posts: oak_planks full height
                   - windows:      brown_stained_glass at Y=2 (mid-row)
                   - top beam:     oak_planks solid at Y=3
  Ceiling/floor  : Y=4  stripped_spruce_log ring + oak_slab (type=top) fill
  Upper storey   : Y=5–7  tapered stair-frame walls (3 layers by default)
                   - each layer the dark_oak_stairs columns step 1 block inward
                   - face infill: oak_planks at corners + brown_glass window centre
  Roof ridge     : Y=8  dark_oak_slab (type=bottom), full Z run at mid_x
  Chimney        : cobblestone column back-left corner, campfire at top
  Interior light : pearlescent_froglight on ceiling (Y=4+1) at centre
"""
from __future__ import annotations

from dataclasses import dataclass
from data.biome_palettes import BiomePalette


@dataclass
class Ctx:
    """All coordinates and dimensions for a single house build."""

    # world-space origin: bottom-left corner of the foundation row
    x: int
    y: int
    z: int

    # outer wall footprint (blocks)
    w: int   # x extent  (reference = 7)
    d: int   # z extent  (reference = 7)

    # lower storey wall height in layers above foundation (reference = 3)
    wall_h: int

    # upper storey
    has_upper: bool
    upper_layers: int   # taper layers (reference = 3)

    # optional features
    has_chimney: bool
    has_porch: bool

    # door face:  0 → z_min face (door faces south, i.e. toward -z viewer)
    #             1 → z_max face (door faces north)
    door_face: int

    palette: BiomePalette

    # ------------------------------------------------------------------
    # Derived Y levels
    # ------------------------------------------------------------------

    @property
    def base_y(self) -> int:
        """Foundation / floor level."""
        return self.y

    @property
    def wall_top_y(self) -> int:
        """Top beam row of the lower storey (inclusive)."""
        return self.y + self.wall_h

    @property
    def ceiling_y(self) -> int:
        """Beam ring + slab ceiling one row above the lower walls."""
        return self.wall_top_y + 1

    @property
    def roof_ridge_y(self) -> int:
        """Y of the roof ridge slab."""
        if self.has_upper:
            return self.ceiling_y + self.upper_layers + 1
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
        """Minecraft facing string for the door block."""
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