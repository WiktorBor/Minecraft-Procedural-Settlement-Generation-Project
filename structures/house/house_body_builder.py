"""
structures/house/house_body_builder.py
----------------------------------------
Body builder for the house shape grammar.

Handles everything below the roof line:

  build_foundation  — perimeter in foundation material, interior in floor material
  build_body        — lower storey walls with window row and top beam
  build_facade      — door face (door + flanking windows)
  build_ceiling     — beam ring + slab fill + central light
  build_upper       — half-timbered upper storey walls above the ceiling

Design
------
Generic geometry (solid rects, hollow walls) is delegated to
structures.base.primitives so there is no duplicated logic here.
Only house-specific decisions live in this file:
  • Window placement that differs per face (facade vs. side)
  • Ceiling beam ring with interior froglight
  • Half-timbered upper storey pattern (accent posts + wall infill)
"""
from __future__ import annotations

import random

from gdpc import Block

from data.biome_palettes import palette_get
from structures.base.primitives import build_ceiling as prim_ceiling
from structures.base.primitives import build_foundation as prim_foundation
from structures.house.house_context import Ctx


class BodyBuilder:

    # ------------------------------------------------------------------
    # Foundation + floor
    # ------------------------------------------------------------------

    def build_foundation(self, ctx: Ctx) -> None:
        """
        Perimeter blocks use the 'foundation' material; interior uses
        'floor' material (with 10 % chance of 'moss' for variety).
        """
        mat_found = ctx.palette["foundation"]
        mat_floor = palette_get(ctx.palette, "floor", "minecraft:oak_planks")
        mat_moss  = palette_get(ctx.palette, "moss",  "minecraft:moss_block")

        found_pos = []
        floor_pos = []
        for dx in range(ctx.w):
            for dz in range(ctx.d):
                pos     = (ctx.x + dx, ctx.base_y, ctx.z + dz)
                on_edge = dx == 0 or dx == ctx.w - 1 or dz == 0 or dz == ctx.d - 1
                (found_pos if on_edge else floor_pos).append(pos)

        ctx.buffer.place_many(found_pos, Block(mat_found))
        for pos in floor_pos:
            mat = mat_moss if random.random() < 0.10 else mat_floor
            ctx.place_block(pos, Block(mat))

        # Embed the structure into terrain
        prim_foundation(ctx, ctx.x, ctx.base_y, ctx.z, ctx.w, ctx.d)

    # ------------------------------------------------------------------
    # Lower storey walls
    # ------------------------------------------------------------------

    def build_body(self, ctx: Ctx) -> None:
        """
        Hollow walls with a window row at mid-height and a solid top beam row.
        The facade face is skipped here — build_facade handles it separately.
        """
        mat_wall   = ctx.palette["wall"]
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")

        win_y = ctx.base_y + (ctx.wall_h // 2) + 1
        top_y = ctx.wall_top_y

        for dy in range(1, ctx.wall_h + 1):
            y      = ctx.base_y + dy
            is_top = (y == top_y)
            is_win = (y == win_y)

            # Z-facing walls (skip door face entirely)
            for dx in range(ctx.w):
                for face_z in (ctx.z, ctx.z + ctx.d - 1):
                    if face_z == ctx.door_z:
                        continue
                    is_corner = dx == 0 or dx == ctx.w - 1
                    if is_corner or is_top:
                        ctx.place_block((ctx.x + dx, y, face_z), Block(mat_wall))
                    elif is_win:
                        ctx.place_block((ctx.x + dx, y, face_z), Block(mat_window))

            # X-facing walls (skip corners already placed above)
            for dz in range(1, ctx.d - 1):
                for face_x in (ctx.x, ctx.x + ctx.w - 1):
                    is_corner_z = dz == 1 or dz == ctx.d - 2
                    if is_corner_z or is_top:
                        ctx.place_block((face_x, y, ctx.z + dz), Block(mat_wall))
                    elif is_win:
                        ctx.place_block((face_x, y, ctx.z + dz), Block(mat_window))

    # ------------------------------------------------------------------
    # Facade (door face)
    # ------------------------------------------------------------------

    def build_facade(self, ctx: Ctx) -> None:
        """
        Door face: solid wall with door opening, flanking windows, top beam.
        Reads 'door' from palette so every biome gets the right door type.
        """
        mat_wall   = ctx.palette["wall"]
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")
        mat_door   = palette_get(ctx.palette, "door",   "minecraft:oak_door")

        win_y  = ctx.base_y + (ctx.wall_h // 2) + 1
        top_y  = ctx.wall_top_y
        face_z = ctx.door_z
        door_x = ctx.door_x

        for dy in range(1, ctx.wall_h + 1):
            y      = ctx.base_y + dy
            is_top = (y == top_y)
            for dx in range(ctx.w):
                x           = ctx.x + dx
                is_corner   = dx == 0 or dx == ctx.w - 1
                is_door_col = x == door_x
                is_win_col  = abs(x - door_x) == 2

                if is_corner or is_top:
                    ctx.place_block((x, y, face_z), Block(mat_wall))
                elif is_door_col and dy in (1, 2):
                    pass  # door blocks placed below
                elif is_win_col and y == win_y:
                    ctx.place_block((x, y, face_z), Block(mat_window))
                else:
                    ctx.place_block((x, y, face_z), Block(mat_wall))

        ctx.place_block(
            (door_x, ctx.base_y + 1, face_z),
            Block(mat_door, {"facing": ctx.door_facing, "half": "lower", "hinge": "left"}),
        )
        ctx.place_block(
            (door_x, ctx.base_y + 2, face_z),
            Block(mat_door, {"facing": ctx.door_facing, "half": "upper", "hinge": "left"}),
        )

    # ------------------------------------------------------------------
    # Ceiling
    # ------------------------------------------------------------------

    def build_ceiling(self, ctx: Ctx) -> None:
        """
        Delegates to the shared build_ceiling primitive so all structures use
        the same beam-ring + slab + size-based light logic.
        """
        prim_ceiling(
            ctx,
            ctx.x, ctx.ceiling_y, ctx.z,
            ctx.w, ctx.d,
            floor_y=ctx.base_y,
        )

    # ------------------------------------------------------------------
    # Upper storey walls
    # ------------------------------------------------------------------

    def build_upper(self, ctx: Ctx) -> None:
        """
        Half-timbered upper storey walls sitting on top of the ceiling ring.

        Pattern:
          • Corner posts and horizontal rails use 'accent' (timber).
          • Infill panels use 'wall'.
          • A window row appears at mid-height of the upper storey.
        """
        mat_wall   = ctx.palette["wall"]
        mat_accent = ctx.palette["accent"]
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")

        for dy in range(1, ctx.upper_h + 1):
            y       = ctx.ceiling_y + dy
            is_rail = (dy % 2 == 0)

            # Z-facing walls
            for dx in range(ctx.w):
                is_post = dx == 0 or dx == ctx.w - 1
                for face_z in (ctx.z, ctx.z + ctx.d - 1):
                    if is_post or is_rail:
                        ctx.place_block((ctx.x + dx, y, face_z), Block(mat_accent))
                    elif dy == ctx.upper_h // 2 + 1:
                        ctx.place_block((ctx.x + dx, y, face_z), Block(mat_window))
                    else:
                        ctx.place_block((ctx.x + dx, y, face_z), Block(mat_wall))

            # X-facing walls
            for dz in range(1, ctx.d - 1):
                for face_x in (ctx.x, ctx.x + ctx.w - 1):
                    if is_rail:
                        ctx.place_block((face_x, y, ctx.z + dz), Block(mat_accent))
                    else:
                        ctx.place_block((face_x, y, ctx.z + dz), Block(mat_wall))

