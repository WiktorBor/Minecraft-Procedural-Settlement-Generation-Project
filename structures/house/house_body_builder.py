"""
Body builder for the house shape grammar.

Handles everything below the roof line:
  build_foundation  — cobblestone perimeter + floor
  build_body        — lower storey walls, windows, top beam
  build_facade      — door face (door + front windows)
  build_ceiling     — stripped_spruce_log ring + oak_slab fill + light
  build_upper       — half-timbered upper storey walls above the ceiling
"""
from __future__ import annotations

import random

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from .house_context import Ctx


class BodyBuilder:

    def __init__(self, editor: Editor, palette: BiomePalette) -> None:
        self.editor  = editor
        self.palette = palette

    # ------------------------------------------------------------------
    # Foundation + floor
    # ------------------------------------------------------------------

    def build_foundation(self, ctx: Ctx) -> None:
        mat_found = ctx.palette["foundation"]
        mat_floor = palette_get(ctx.palette, "floor", "minecraft:oak_planks")
        mat_moss  = palette_get(ctx.palette, "moss",  "minecraft:moss_block")

        found_pos = []
        floor_pos = []
        for dx in range(ctx.w):
            for dz in range(ctx.d):
                pos    = (ctx.x + dx, ctx.base_y, ctx.z + dz)
                on_edge = dx == 0 or dx == ctx.w-1 or dz == 0 or dz == ctx.d-1
                (found_pos if on_edge else floor_pos).append(pos)

        ctx.editor.placeBlock(found_pos, Block(mat_found))
        for pos in floor_pos:
            mat = mat_moss if random.random() < 0.10 else mat_floor
            ctx.editor.placeBlock(pos, Block(mat))

    # ------------------------------------------------------------------
    # Lower storey walls
    # ------------------------------------------------------------------

    def build_body(self, ctx: Ctx) -> None:
        mat_wall   = ctx.palette["wall"]
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")

        win_y = ctx.base_y + (ctx.wall_h // 2) + 1
        top_y = ctx.wall_top_y

        for dy in range(1, ctx.wall_h + 1):
            y      = ctx.base_y + dy
            is_top = (y == top_y)
            is_win = (y == win_y)

            # Z faces (south + north)
            for dx in range(ctx.w):
                for face_z in [ctx.z, ctx.z + ctx.d - 1]:
                    if face_z == ctx.door_z:
                        continue
                    is_corner = dx == 0 or dx == ctx.w - 1
                    if is_corner or is_top:
                        ctx.editor.placeBlock((ctx.x + dx, y, face_z), Block(mat_wall))
                    elif is_win:
                        ctx.editor.placeBlock((ctx.x + dx, y, face_z), Block(mat_window))

            # X faces (east + west), excluding corners already placed
            for dz in range(1, ctx.d - 1):
                for face_x in [ctx.x, ctx.x + ctx.w - 1]:
                    is_corner_z = dz == 1 or dz == ctx.d - 2
                    if is_corner_z or is_top:
                        ctx.editor.placeBlock((face_x, y, ctx.z + dz), Block(mat_wall))
                    elif is_win:
                        ctx.editor.placeBlock((face_x, y, ctx.z + dz), Block(mat_window))

    # ------------------------------------------------------------------
    # Facade (door face)
    # ------------------------------------------------------------------

    def build_facade(self, ctx: Ctx) -> None:
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
                    ctx.editor.placeBlock((x, y, face_z), Block(mat_wall))
                elif is_door_col and dy in (1, 2):
                    pass   # door placed below
                elif is_win_col and y == win_y:
                    ctx.editor.placeBlock((x, y, face_z), Block(mat_window))
                else:
                    ctx.editor.placeBlock((x, y, face_z), Block(mat_wall))

        # Door blocks
        ctx.editor.placeBlock(
            (door_x, ctx.base_y + 1, face_z),
            Block(mat_door, {"facing": ctx.door_facing, "half": "lower", "hinge": "left"}),
        )
        ctx.editor.placeBlock(
            (door_x, ctx.base_y + 2, face_z),
            Block(mat_door, {"facing": ctx.door_facing, "half": "upper", "hinge": "left"}),
        )

    # ------------------------------------------------------------------
    # Ceiling
    # ------------------------------------------------------------------

    def build_ceiling(self, ctx: Ctx) -> None:
        mat_beam    = palette_get(ctx.palette, "accent_beam",     "minecraft:stripped_spruce_log")
        mat_ceiling = palette_get(ctx.palette, "ceiling_slab",    "minecraft:oak_slab")
        mat_light   = palette_get(ctx.palette, "interior_light",  "minecraft:pearlescent_froglight")

        cy = ctx.ceiling_y
        beam_pos = []
        ceil_pos = []
        for dx in range(ctx.w):
            for dz in range(ctx.d):
                pos     = (ctx.x + dx, cy, ctx.z + dz)
                on_edge = dx == 0 or dx == ctx.w-1 or dz == 0 or dz == ctx.d-1
                (beam_pos if on_edge else ceil_pos).append(pos)

        ctx.editor.placeBlock(beam_pos, Block(mat_beam))
        ctx.editor.placeBlock(ceil_pos, Block(mat_ceiling, {"type": "top"}))
        ctx.editor.placeBlock((ctx.mid_x, cy, ctx.mid_z), Block(mat_light))

    # ------------------------------------------------------------------
    # Upper storey walls
    # ------------------------------------------------------------------

    def build_upper(self, ctx: Ctx) -> None:
        """
        Half-timbered upper storey walls sitting on top of the ceiling ring,
        rising ctx.upper_h layers.  Same hollow-box logic as the lower storey
        but using accent timber for corner posts and horizontal rails.
        """
        mat_wall   = ctx.palette["wall"]
        mat_accent = ctx.palette["accent"]
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")

        for dy in range(1, ctx.upper_h + 1):
            y       = ctx.ceiling_y + dy
            is_rail = (dy % 2 == 0)

            # Z faces
            for dx in range(ctx.w):
                is_post = dx == 0 or dx == ctx.w - 1
                for face_z in [ctx.z, ctx.z + ctx.d - 1]:
                    if is_post or is_rail:
                        ctx.editor.placeBlock((ctx.x + dx, y, face_z), Block(mat_accent))
                    elif dy == ctx.upper_h // 2 + 1:
                        # Window row at mid-height of upper storey
                        ctx.editor.placeBlock((ctx.x + dx, y, face_z), Block(mat_window))
                    else:
                        ctx.editor.placeBlock((ctx.x + dx, y, face_z), Block(mat_wall))

            # X faces
            for dz in range(1, ctx.d - 1):
                for face_x in [ctx.x, ctx.x + ctx.w - 1]:
                    if is_rail:
                        ctx.editor.placeBlock((face_x, y, ctx.z + dz), Block(mat_accent))
                    else:
                        ctx.editor.placeBlock((face_x, y, ctx.z + dz), Block(mat_wall))