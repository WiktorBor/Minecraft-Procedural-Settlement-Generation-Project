"""
Detail builder for the house shape grammar.

Matches the reference house (small_house.nbt):

Chimney
  cobblestone column in the back-left corner, rising from base_y to
  roof_ridge_y, with a campfire on top.

Interior furniture  (placed at Y = base_y + 1 inside the walls)
  Bed (red_bed, 2-block, east-facing) near the back-right corner.
  Crafting table near the back-left corner.
  Decorated pot on the right wall.
  Cave vines hanging from the ceiling (at ceiling_y, centre).

Exterior details
  Lantern above the door (wall face, hanging=false).
  Spruce fence post flanking the door (porch flag).
  Pink petals / wildflowers on the ground in front of the door.
  Moss carpet scattered on the interior floor.
  Potted plant (flowering azalea) on the window sill.
"""
from __future__ import annotations

import random

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from .house_context import Ctx


class DetailBuilder:

    def __init__(self, editor: Editor, palette: BiomePalette) -> None:
        self.editor  = editor
        self.palette = palette

    # ------------------------------------------------------------------
    # Chimney
    # ------------------------------------------------------------------

    def build_chimney(self, ctx: Ctx) -> None:
        """
        Cobblestone column in the back-left corner (x = x0+2, z = back-2),
        rising from base_y up to roof_ridge_y, with campfire on top.
        """
        mat_found = ctx.palette["foundation"]   # cobblestone

        # Back-left corner position (1 block from each back/left edge)
        cx = ctx.x + 1
        cz = ctx.back_z - (1 if ctx.door_face == 0 else -1)

        column = [(cx, y, cz) for y in range(ctx.base_y, ctx.roof_ridge_y + 1)]
        self.editor.placeBlock(column, Block(mat_found))

        # Campfire on top
        mat_smoke   = palette_get(ctx.palette, "smoke", "minecraft:campfire")
        smoke_props = (
            {"lit": "true", "signal_fire": "false", "facing": "north"}
            if "campfire" in mat_smoke else {}
        )
        self.editor.placeBlock(
            (cx, ctx.roof_ridge_y + 1, cz),
            Block(mat_smoke, smoke_props),
        )

    # ------------------------------------------------------------------
    # Interior furniture
    # ------------------------------------------------------------------

    def build_interior(self, ctx: Ctx) -> None:
        """
        Place interior furniture matching the reference:
          - Bed (2-block, east-facing) in the back-right area
          - Crafting table near the back-left corner
          - Decorated pot on the right wall
          - Cave vines at ceiling centre
          - Moss carpet patches on the floor
        """
        fy     = ctx.base_y + 1   # furniture Y (1 above floor)
        bk_z   = ctx.back_z
        step   = 1 if ctx.door_face == 0 else -1   # direction toward interior

        # --- Bed (foot + head, east-facing) ---
        bed_x = ctx.x + ctx.w - 4   # foot at x0+3 from left edge
        bed_z = bk_z - step * 2
        if ctx.z < bed_z < ctx.z + ctx.d - 1:
            self.editor.placeBlock(
                (bed_x, fy, bed_z),
                Block("minecraft:red_bed", {"facing": "east", "part": "foot", "occupied": "false"}),
            )
            self.editor.placeBlock(
                (bed_x + 1, fy, bed_z),
                Block("minecraft:red_bed", {"facing": "east", "part": "head", "occupied": "false"}),
            )

        # --- Crafting table ---
        ct_x = ctx.x + 1   # x0+1 from left edge
        ct_z = bk_z - step * 1
        if ctx.z < ct_z < ctx.z + ctx.d - 1:
            self.editor.placeBlock((ct_x, fy, ct_z), Block("minecraft:crafting_table"))

        # --- Decorated pot on the right wall ---
        pot_x = ctx.x + ctx.w - 2
        pot_z = bk_z - step * 1
        if ctx.z < pot_z < ctx.z + ctx.d - 1:
            self.editor.placeBlock(
                (pot_x, fy, pot_z),
                Block("minecraft:decorated_pot", {"facing": "east"}),
            )

        # --- Cave vines at ceiling centre (hanging down from ceiling_y) ---
        self.editor.placeBlock(
            (ctx.mid_x, ctx.ceiling_y, ctx.mid_z),
            Block("minecraft:cave_vines", {"berries": "true", "age": "25"}),
        )

        # --- Moss carpet patches inside (3–5 random spots) ---
        mat_moss = palette_get(ctx.palette, "moss", "minecraft:moss_carpet")
        for _ in range(random.randint(3, 5)):
            mx = random.randint(ctx.x + 1, ctx.x + ctx.w - 2)
            mz = random.randint(ctx.z + 1, ctx.z + ctx.d - 2)
            self.editor.placeBlock((mx, ctx.base_y + 1, mz), Block(mat_moss))

    # ------------------------------------------------------------------
    # Exterior details
    # ------------------------------------------------------------------

    def build_details(self, ctx: Ctx) -> None:
        """
        Exterior decorations:
          - Lantern above door
          - Fence post porch pillars (if has_porch)
          - Flowers on the ground in front of the door
          - Potted azalea on window sill
        """
        face_z    = ctx.door_z
        outside_z = face_z + (-1 if ctx.door_face == 0 else 1)
        door_x    = ctx.door_x
        base_y    = ctx.base_y

        # --- Lantern above door ---
        mat_lantern = palette_get(ctx.palette, "light", "minecraft:lantern")
        self.editor.placeBlock(
            (door_x, base_y + ctx.wall_h, face_z),
            Block(mat_lantern, {"hanging": "false"}),
        )

        # --- Porch fence posts flanking the door ---
        if ctx.has_porch:
            mat_fence = palette_get(ctx.palette, "fence", "minecraft:spruce_fence")
            for fx in [door_x - 1, door_x + 1]:
                for fy in [base_y + 1, base_y + 2]:
                    self.editor.placeBlock((fx, fy, outside_z), Block(mat_fence))

        # --- Ground flowers in front of door ---
        flower = random.choice([
            ("minecraft:pink_petals",  {"facing": "north", "flower_amount": "2"}),
            ("minecraft:wildflowers",  {"facing": "north", "flower_amount": "4"}),
            ("minecraft:short_grass",  {}),
        ])
        self.editor.placeBlock((door_x, base_y, outside_z), Block(flower[0], flower[1]))

        # --- Potted flowering azalea on front window sill ---
        win_sill_x = door_x + 2
        if ctx.x < win_sill_x < ctx.x + ctx.w - 1:
            self.editor.placeBlock(
                (win_sill_x, base_y + 1, face_z),
                Block("minecraft:potted_flowering_azalea_bush"),
            )