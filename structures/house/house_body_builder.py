"""
Body builder for the house shape grammar.

Matches the reference house (small_house.nbt):

  Foundation  Y=base_y    cobblestone perimeter ring
  Floor       Y=base_y    oak_planks interior (random moss_block spots)
  Walls       Y=base_y+1  to  wall_top_y
                - corner posts: wall material, full height
                - window row (mid layer): glass pane centred on each face
                - top beam (wall_top_y): solid wall material
  Facade      door (lower+upper half) + front windows at window row
              door lintel slab at wall_top_y
  Ceiling     Y=ceiling_y
                - perimeter ring: accent_beam material (stripped_spruce_log)
                - interior fill: ceiling_slab (oak_slab type=top)
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
    # Foundation
    # ------------------------------------------------------------------

    def build_foundation(self, ctx: Ctx) -> None:
        """
        Cobblestone perimeter ring at base_y + oak_planks interior floor.
        A few interior blocks are randomly replaced with moss_block for
        the same natural variation seen in the reference house.
        """
        mat_found = ctx.palette["foundation"]
        mat_floor = palette_get(ctx.palette, "floor", "minecraft:oak_planks")
        mat_moss  = palette_get(ctx.palette, "moss",  "minecraft:moss_block")

        positions_found = []
        positions_floor = []

        for dx in range(ctx.w):
            for dz in range(ctx.d):
                pos = (ctx.x + dx, ctx.base_y, ctx.z + dz)
                on_edge = (dx == 0 or dx == ctx.w - 1 or dz == 0 or dz == ctx.d - 1)
                if on_edge:
                    positions_found.append(pos)
                else:
                    positions_floor.append(pos)

        self.editor.placeBlock(positions_found, Block(mat_found))

        # Place floor with occasional moss variation (≈10 % of interior tiles)
        for pos in positions_floor:
            if random.random() < 0.10:
                self.editor.placeBlock(pos, Block(mat_moss))
            else:
                self.editor.placeBlock(pos, Block(mat_floor))

    # ------------------------------------------------------------------
    # Walls (lower storey)
    # ------------------------------------------------------------------

    def build_body(self, ctx: Ctx) -> None:
        """
        Lower storey walls matching the reference:
          - Full-height corner posts (wall material)
          - Window panes at the mid-height row on non-door faces
          - Top beam row (wall_top_y): solid wall material on all faces
          - Door face left open (facade fills it)
        """
        mat_wall   = ctx.palette["wall"]
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")

        win_y  = ctx.base_y + (ctx.wall_h // 2) + 1   # mid-height window row
        top_y  = ctx.wall_top_y

        for dy in range(1, ctx.wall_h + 1):
            y        = ctx.base_y + dy
            is_top   = (y == top_y)
            is_win   = (y == win_y)

            for dx in range(ctx.w):
                for face_z in [ctx.z, ctx.z + ctx.d - 1]:
                    is_corner = (dx == 0 or dx == ctx.w - 1)
                    is_door_face = (face_z == ctx.door_z)

                    if is_door_face:
                        continue   # facade handles this face entirely

                    if is_corner or is_top:
                        self.editor.placeBlock((ctx.x + dx, y, face_z), Block(mat_wall))
                    elif is_win:
                        self.editor.placeBlock((ctx.x + dx, y, face_z), Block(mat_window))
                    # else: air (open interior panels)

            for dz in range(1, ctx.d - 1):
                for face_x in [ctx.x, ctx.x + ctx.w - 1]:
                    is_corner_z = (dz == 1 or dz == ctx.d - 2)
                    if is_corner_z or is_top:
                        self.editor.placeBlock((face_x, y, ctx.z + dz), Block(mat_wall))
                    elif is_win:
                        self.editor.placeBlock((face_x, y, ctx.z + dz), Block(mat_window))

    # ------------------------------------------------------------------
    # Facade (door face)
    # ------------------------------------------------------------------

    def build_facade(self, ctx: Ctx) -> None:
        """
        Door face:
          - Corner posts (solid wall)
          - Door (lower + upper) at mid-x
          - Windows flanking the door at win_y
          - Solid wall on remaining cells
          - Top beam at wall_top_y
        """
        mat_wall   = ctx.palette["wall"]
        mat_window = palette_get(ctx.palette, "window", "minecraft:brown_stained_glass")
        mat_door   = palette_get(ctx.palette, "door",   "minecraft:oak_door")
        mat_slab   = palette_get(ctx.palette, "slab",   "minecraft:dark_oak_slab")

        win_y  = ctx.base_y + (ctx.wall_h // 2) + 1
        top_y  = ctx.wall_top_y
        face_z = ctx.door_z
        door_x = ctx.door_x

        for dy in range(1, ctx.wall_h + 1):
            y      = ctx.base_y + dy
            is_top = (y == top_y)

            for dx in range(ctx.w):
                x          = ctx.x + dx
                is_corner  = (dx == 0 or dx == ctx.w - 1)
                is_door_col = (x == door_x)
                is_win_col  = (abs(x - door_x) == 2)

                if is_corner or is_top:
                    self.editor.placeBlock((x, y, face_z), Block(mat_wall))
                elif is_door_col and dy in (1, 2):
                    pass   # door blocks placed below
                elif is_win_col and y == win_y:
                    self.editor.placeBlock((x, y, face_z), Block(mat_window))
                else:
                    self.editor.placeBlock((x, y, face_z), Block(mat_wall))

        # Door lower + upper halves
        self.editor.placeBlock(
            (door_x, ctx.base_y + 1, face_z),
            Block(mat_door, {"facing": ctx.door_facing, "half": "lower", "hinge": "left"}),
        )
        self.editor.placeBlock(
            (door_x, ctx.base_y + 2, face_z),
            Block(mat_door, {"facing": ctx.door_facing, "half": "upper", "hinge": "left"}),
        )

    # ------------------------------------------------------------------
    # Ceiling / upper floor
    # ------------------------------------------------------------------

    def build_ceiling(self, ctx: Ctx) -> None:
        """
        Y = ceiling_y:
          - Perimeter ring: stripped_spruce_log (accent_beam) — matches
            the horizontal beam ring seen at Y=4 in the reference.
          - Interior: oak_slab type=top (ceiling seen from below).
          - Centre tile: pearlescent_froglight as interior light source.
        """
        mat_beam    = palette_get(ctx.palette, "accent_beam", "minecraft:stripped_spruce_log")
        mat_ceiling = palette_get(ctx.palette, "ceiling_slab","minecraft:oak_slab")
        mat_light   = palette_get(ctx.palette, "interior_light", "minecraft:pearlescent_froglight")

        cy = ctx.ceiling_y

        beam_pos    = []
        ceiling_pos = []

        for dx in range(ctx.w):
            for dz in range(ctx.d):
                pos      = (ctx.x + dx, cy, ctx.z + dz)
                on_edge  = (dx == 0 or dx == ctx.w - 1 or dz == 0 or dz == ctx.d - 1)
                if on_edge:
                    beam_pos.append(pos)
                else:
                    ceiling_pos.append(pos)

        self.editor.placeBlock(beam_pos,    Block(mat_beam))
        self.editor.placeBlock(ceiling_pos, Block(mat_ceiling, {"type": "top"}))

        # Interior ceiling light at centre
        light_pos = (ctx.mid_x, cy, ctx.mid_z)
        light_props = {"axis": "x"} if "log" in mat_light else {}
        self.editor.placeBlock(light_pos, Block(mat_light, light_props))