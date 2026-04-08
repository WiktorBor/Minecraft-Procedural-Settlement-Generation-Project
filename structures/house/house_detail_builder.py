"""
structures/house/house_detail_builder.py
-----------------------------------------
Detail builder for the house shape grammar.

Chimney
  Foundation-material column in the back-left corner, rising from
  ceiling_y to the roof ridge, with a campfire on top.

Interior furniture  (Y = base_y + 1, inside the walls)
  Bed       — red_bed, 2-block, east-facing, back-right area
  Crafting  — crafting_table near back-left corner
  Pot       — decorated_pot on the right wall
  Vines     — cave_vines hanging from ceiling centre
  Moss      — moss carpet scattered on floor (3–5 random spots)

Exterior details
  Lantern   — above the door, using place_light for safe hanging state
  Porch     — spruce fence posts flanking the door (when has_porch)
  Flowers   — pink petals / wildflowers / short grass in front of door
  Azalea    — potted flowering azalea on the front window sill
"""
from __future__ import annotations

import random

from gdpc import Block

from gdpc import Block

from palette.palette_system import palette_get
from structures.house.house_context import Ctx


class DetailBuilder:

    # ------------------------------------------------------------------
    # Chimney
    # ------------------------------------------------------------------

    def build_chimney(self, ctx: Ctx) -> None:
        """
        Foundation-material column in the back-left corner (x+1, back_z±1),
        rising from ceiling_y to above the roof ridge, with a campfire on top.
        """
        mat_found = ctx.palette["foundation"]
        cx        = ctx.x + 1
        offset    = 1 if ctx.door_face == 0 else -1
        cz        = ctx.back_z - offset

        top_y = (
            max(ctx.roof_base_y, ctx.upper_top_y) + ctx.d // 2
            if ctx.d > ctx.w
            else max(ctx.roof_base_y, ctx.upper_top_y) + ctx.w // 2
        )

        chimney_blk = Block(mat_found)
        for y in range(ctx.ceiling_y + 1, top_y + 2):
            ctx.place_block((cx, y, cz), chimney_blk)

        mat_smoke   = palette_get(ctx.palette, "smoke", "minecraft:campfire")
        smoke_props = (
            {"lit": "true", "signal_fire": "false", "facing": "north"}
            if "campfire" in mat_smoke else {}
        )
        ctx.place_block((cx, top_y + 1, cz), Block(mat_smoke, smoke_props))

    # ------------------------------------------------------------------
    # Interior furniture
    # ------------------------------------------------------------------

    def build_interior(self, ctx: Ctx) -> None:
        """
        Place interior furniture: bed, crafting table, decorated pot,
        cave vines at ceiling centre, and moss carpet patches on the floor.
        """
        fy   = ctx.base_y + 1
        bk_z = ctx.back_z
        step = 1 if ctx.door_face == 0 else -1

        # Bed (foot + head, east-facing)
        bed_x = ctx.x + ctx.w - 4
        bed_z = bk_z - step * 2
        if ctx.z < bed_z < ctx.z + ctx.d - 1:
            ctx.place_block(
                (bed_x,     fy, bed_z),
                Block("minecraft:red_bed", {"facing": "east", "part": "foot", "occupied": "false"}),
            )
            ctx.place_block(
                (bed_x + 1, fy, bed_z),
                Block("minecraft:red_bed", {"facing": "east", "part": "head", "occupied": "false"}),
            )

        # Crafting table
        ct_z = bk_z - step * 1
        if ctx.z < ct_z < ctx.z + ctx.d - 1:
            ctx.place_block((ctx.x + 1, fy, ct_z), Block("minecraft:crafting_table"))

        # Decorated pot
        pot_x = ctx.x + ctx.w - 2
        pot_z = bk_z - step * 1
        if ctx.z < pot_z < ctx.z + ctx.d - 1:
            ctx.place_block(
                (pot_x, fy, pot_z),
                Block("minecraft:decorated_pot", {"facing": "east"}),
            )

        # Cave vines hanging from ceiling centre
        ctx.place_block(
            (ctx.mid_x, ctx.ceiling_y, ctx.mid_z),
            Block("minecraft:cave_vines", {"berries": "true", "age": "25"}),
        )

        # Moss carpet patches (3–5 random spots inside the walls)
        mat_moss = palette_get(ctx.palette, "moss", "minecraft:moss_carpet")
        for _ in range(random.randint(3, 5)):
            mx = random.randint(ctx.x + 1, ctx.x + ctx.w - 2)
            mz = random.randint(ctx.z + 1, ctx.z + ctx.d - 2)
            ctx.place_block((mx, ctx.base_y + 1, mz), Block(mat_moss))

    # ------------------------------------------------------------------
    # Exterior details
    # ------------------------------------------------------------------

    def build_details(self, ctx: Ctx) -> None:
        """
        Exterior decorations: lantern above door, optional porch fence
        posts, ground flowers, and a potted azalea on the window sill.
        """
        face_z    = ctx.door_z
        outside_z = face_z + (-1 if ctx.door_face == 0 else 1)
        door_x    = ctx.door_x
        base_y    = ctx.base_y

        # Lantern above door
        mat_lantern = palette_get(ctx.palette, "light", "minecraft:lantern")
        hanging = "lantern" in mat_lantern
        ctx.place_block(
            (door_x, base_y + ctx.wall_h, face_z),
            Block(mat_lantern, {"hanging": "true"} if hanging else {}),
        )

        # Porch fence posts flanking the door
        if ctx.has_porch:
            mat_fence = palette_get(ctx.palette, "fence", "minecraft:spruce_fence")
            for fx in (door_x - 1, door_x + 1):
                for fy in (base_y + 1, base_y + 2):
                    ctx.place_block((fx, fy, outside_z), Block(mat_fence))

        # Ground flowers in front of the door
        flower_id, flower_props = random.choice([
            ("minecraft:pink_petals",  {"facing": "north", "flower_amount": "2"}),
            ("minecraft:wildflowers",  {"facing": "north", "flower_amount": "4"}),
            ("minecraft:short_grass",  {}),
        ])
        ctx.place_block((door_x, base_y, outside_z), Block(flower_id, flower_props))

        # Potted flowering azalea on the front window sill
        win_sill_x = door_x + 2
        if ctx.x < win_sill_x < ctx.x + ctx.w - 1:
            ctx.place_block(
                (win_sill_x, base_y + 1, face_z - 1),
                Block("minecraft:potted_flowering_azalea_bush"),
            )