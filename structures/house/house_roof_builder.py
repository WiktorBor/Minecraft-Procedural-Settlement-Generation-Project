"""
Roof builder for the house shape grammar.

Matches the reference house (small_house.nbt) upper storey + roof:

Upper storey (Y = ceiling_y+1  to  ceiling_y+upper_layers)
------------------------------------------------------------
Each layer the dark_oak_stairs eave columns step 1 block inward from the
previous layer.  Layer 0 starts at x=x0+1 and x=x1-1 (just inside the
ceiling beam ring).

  Layer i:
    - dark_oak_stairs at (x0+1+i, y, z) for all z in [z0-1 .. z1+1]
      and (x1-1-i, y, z) for all z in [z0-1 .. z1+1]
      → stair facing outward (east / west), shape varies at corners
    - Face infill between the two stair columns (south/north faces only):
        oak_planks at corners, brown_glass pane at centre column(s)

Roof ridge (Y = roof_ridge_y)
------------------------------
  dark_oak_slab (type=bottom) at mid_x, for all z in [z0 .. z1]

The result is a stepped pyramid gable that converges on a single ridge
column — exactly matching the NBT reference.
"""
from __future__ import annotations

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from .house_context import Ctx


class RoofBuilder:

    def __init__(self, editor: Editor, palette: BiomePalette) -> None:
        self.editor  = editor
        self.palette = palette

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, ctx: Ctx) -> None:
        if ctx.has_upper:
            self._build_upper_storey(ctx)
        self._build_ridge(ctx)

    # ------------------------------------------------------------------
    # Upper storey — tapered stair-frame
    # ------------------------------------------------------------------

    def _build_upper_storey(self, ctx: Ctx) -> None:
        """
        Each layer i (0-indexed) of the upper storey:
          - Stair columns at x = x0+1+i and x = x1-1-i, spanning full Z width
            including 1-block overhang outside the footprint (matching the eave)
          - On south/north faces: corner oak_planks + glass pane(s) between
        """
        mat_stair  = ctx.palette["roof"]                   # dark_oak_stairs
        mat_wall   = ctx.palette["wall"]                   # oak_planks
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")

        x0 = ctx.x
        x1 = ctx.x + ctx.w - 1
        z0 = ctx.z
        z1 = ctx.z + ctx.d - 1
        # Stair columns span 1 block outside the footprint on both Z sides
        z_span_lo = z0 - 1
        z_span_hi = z1 + 1

        # Eave overhang at ceiling_y: stair columns sit 1 block OUTSIDE the footprint
        for dz in range(z_span_lo, z_span_hi + 1):
            self.editor.placeBlock(
                (x0 - 1, ctx.ceiling_y, dz),
                Block(mat_stair, {"facing": "east", "half": "bottom",
                                  "shape": self._stair_shape(dz, z0, z1, "east")}),
            )
            self.editor.placeBlock(
                (x1 + 1, ctx.ceiling_y, dz),
                Block(mat_stair, {"facing": "west", "half": "bottom",
                                  "shape": self._stair_shape(dz, z0, z1, "west")}),
            )

        for i in range(ctx.upper_layers):
            y      = ctx.ceiling_y + 1 + i
            col_lo = x0 + i       # west stair column (layer 0 starts at wall edge)
            col_hi = x1 - i       # east stair column

            if col_lo > col_hi:
                break   # footprint too narrow — stop early

            # West stair column (facing east = stepping up to the right)
            for dz in range(z_span_lo, z_span_hi + 1):
                self.editor.placeBlock(
                    (col_lo, y, dz),
                    Block(mat_stair, {"facing": "east", "half": "bottom",
                                      "shape": self._stair_shape(dz, z0, z1, "east")}),
                )

            # East stair column (facing west = stepping up to the left)
            for dz in range(z_span_lo, z_span_hi + 1):
                self.editor.placeBlock(
                    (col_hi, y, dz),
                    Block(mat_stair, {"facing": "west", "half": "bottom",
                                      "shape": self._stair_shape(dz, z0, z1, "west")}),
                )

            # Face infill on south and north walls between the two stair columns
            for face_z in (z0, z1):
                for x in range(col_lo + 1, col_hi):
                    # Columns immediately adjacent to stairs are planks; centre is glass
                    is_edge = (x == col_lo + 1 or x == col_hi - 1)
                    mat = mat_wall if is_edge else mat_window
                    self.editor.placeBlock((x, y, face_z), Block(mat))
    def _stair_shape(self, dz: int, z0: int, z1: int, facing: str) -> str:
        """
        Return the correct stair shape at position dz along the Z run,
        producing inner_left / inner_right corners at z0 and z1 and
        straight everywhere else.
        """
        if dz == z0:
            return "inner_left"  if facing == "east" else "inner_right"
        if dz == z1:
            return "inner_right" if facing == "east" else "inner_left"
        return "straight"

    # ------------------------------------------------------------------
    # Roof ridge
    # ------------------------------------------------------------------

    def _build_ridge(self, ctx: Ctx) -> None:
        """
        dark_oak_slab (type=bottom) at mid_x, spanning the full Z footprint.
        """
        mat_slab = palette_get(ctx.palette, "roof_slab", "minecraft:dark_oak_slab")
        ridge_y  = ctx.roof_ridge_y
        mid_x    = ctx.mid_x

        ridge_pos = [
            (mid_x, ridge_y, ctx.z + dz)
            for dz in range(ctx.d)
        ]
        self.editor.placeBlock(ridge_pos, Block(mat_slab, {"type": "bottom"}))