"""
structures/misc/blacksmith.py
------------------------------
Procedural medieval blacksmith — two connected wings + chimney.

Reference: KoalaBuilds Medieval Blacksmith screenshot.

Layout (plan view, door facing south)
--------------------------------------

    ← left_w →  1  ← right_w →
    ┌──────────┬─┬────────────┐  ─┐
    │          │C│  OPEN      │   │  forge_d
    │  LIVING  │H│  PORCH     │  ─┤
    │  WING    │I│  (pillars) │   │
    │  (tall,  │M│────────────┤  ─┤
    │  plaster)│N│  WORK AREA │   │  work_d
    │          │Y│  (stone)   │   │
    └──────────┴─┴────────────┘  ─┘

Wing details
------------
  Left  — residential quarter.
           Wall material: calcite / white plaster.
           Oak log corner posts + horizontal mid-beam (half-timbered look).
           Wall height 5, gabled roof, centred door on south face,
           windows on south + side faces.
           Interior: crafting table, chest, bookshelf, flower pot.

  Right — forge wing.
           Wall material: cobblestone (lower), stone bricks (upper).
           Wall height 4, gabled roof.
           South face open: 3 oak log pillars + overhead beam + hanging lanterns.
           Partition wall with doorway between porch and enclosed work area.
           Interior: blast furnace, anvil, barrel, grindstone, smoker.

  Chimney — 2-wide cobblestone→stone-brick column between the two wings.
            Rises well above both roof peaks. Campfire on top.

  Connector — oak log beam bridging the gap at shared eave height,
              plus a fence/gate section at ground level.
"""
from __future__ import annotations

import random

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from structures.base.build_context import place_light
from structures.roofs.roof_builder import _RoofCorners, build_gabled_roof


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

class Blacksmith:
    """
    Medieval blacksmith with two connected wings and a central chimney.

    Recommended plot: width >= 13, depth >= 10.
    Scales down gracefully for smaller plots (minimum 9 × 8).
    """

    def build(
        self,
        editor: Editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
    ) -> None:
        x, y, z = plot.x, plot.y, plot.z
        w, d    = plot.width, plot.depth

        if w < 9 or d < 8:
            return  # too small for a two-wing structure

        # --- Width split ---
        left_w = max(5, (w * 6) // 10)
        if left_w % 2 == 0:
            left_w -= 1          # keep odd for centred door / ridge
        right_w = w - left_w - 1  # -1 for the chimney column
        if right_w % 2 == 0:
            right_w -= 1

        left_x  = x
        chim_x  = x + left_w          # single-column chimney
        right_x = x + left_w + 1

        # --- Depth split for forge wing ---
        forge_d = max(3, d // 3)       # open porch
        work_d  = d - forge_d          # enclosed work area

        # --- Heights ---
        left_h  = 5   # living wing
        right_h = 4   # forge wing

        b = _Builder(editor, palette)
        b.living_wing(left_x,  y, z, left_w, d,       left_h)
        b.forge_wing( right_x, y, z, right_w, d,       right_h, forge_d, work_d)
        b.chimney(    chim_x,  y, z, d,                left_h, right_h)
        b.connector(  left_x,  y, z, left_w, right_w,  left_h, right_h)


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------

class _Builder:

    def __init__(self, editor: Editor, palette: BiomePalette) -> None:
        self.e  = editor
        self.p  = palette

        # Materials — fall back to sensible defaults if palette key missing
        self.log      = palette_get(palette, "accent_beam", "minecraft:oak_log")
        self.plank    = palette_get(palette, "floor",       "minecraft:oak_planks")
        self.plaster  = palette_get(palette, "plaster",     "minecraft:calcite")
        self.cobble   = palette_get(palette, "foundation",  "minecraft:cobblestone")
        self.stone_br = "minecraft:stone_bricks"
        self.wall_r   = palette_get(palette, "wall",        "minecraft:cobblestone")
        self.roof_mat = palette_get(palette, "roof",        "minecraft:spruce_stairs")
        self.roof_slab= palette_get(palette, "roof_slab",   "minecraft:spruce_slab")
        self.window   = palette_get(palette, "window",      "minecraft:glass_pane")
        self.door_mat = palette_get(palette, "door",        "minecraft:oak_door")
        self.lantern  = palette_get(palette, "light",       "minecraft:lantern")
        self.fence    = palette_get(palette, "fence",       "minecraft:oak_fence")

    # ------------------------------------------------------------------
    # Living wing
    # ------------------------------------------------------------------

    def living_wing(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        wall_h: int,
    ) -> None:
        e = self.e

        # Foundation (2 deep, clamped above world floor y=-64)
        if y - 1 >= -64:
            self._layer(x, y - 1, z, w, d, self.cobble)
        if y - 2 >= -64:
            self._layer(x, y - 2, z, w, d, self.cobble)

        # Floor
        self._layer(x, y, z, w, d, self.plank)

        # Walls with oak log corner posts and a mid-height horizontal beam
        beam_y = y + wall_h // 2 + 1
        for dy in range(1, wall_h + 1):
            wy = y + dy
            # South + north faces
            for dx in range(w):
                for fz in (z, z + d - 1):
                    corner = (dx == 0 or dx == w - 1)
                    on_beam = (wy == beam_y)
                    mat = self.log if (corner or on_beam) else self.plaster
                    e.placeBlock((x + dx, wy, fz), Block(mat))
            # East + west faces (skip corners already placed)
            for dz in range(1, d - 1):
                for fx in (x, x + w - 1):
                    corner_z = (dz == 1 or dz == d - 2)
                    on_beam  = (wy == beam_y)
                    mat = self.log if (corner_z or on_beam) else self.plaster
                    e.placeBlock((fx, wy, z + dz), Block(mat))

        # Door — centred on south face
        self._door(x + w // 2, y, z, "south")

        # Windows
        win_y = y + 2
        # South face — flank the door
        for wx in (x + w // 2 - 2, x + w // 2 + 2):
            if x < wx < x + w - 1:
                e.placeBlock((wx, win_y, z), Block(self.window))
        # Side faces — mid-depth
        mid_z = z + d // 2
        e.placeBlock((x,         win_y, mid_z), Block(self.window))
        e.placeBlock((x + w - 1, win_y, mid_z), Block(self.window))

        # Lantern above door (hanging on the outside)
        place_light(e, (x + w // 2, y + wall_h - 1, z - 1), self.lantern, hanging=True)

        # Gabled roof
        self._roof(x, y + wall_h + 1, z, w, d)

        # Interior
        fy  = y + 1
        bkz = z + d - 2
        e.placeBlock((x + 1,     fy, bkz), Block("minecraft:crafting_table"))
        e.placeBlock((x + w - 2, fy, bkz), Block("minecraft:chest", {"facing": "south"}))
        if d >= 6:
            e.placeBlock((x + w - 1, fy,     z + d // 2), Block("minecraft:bookshelf"))
            e.placeBlock((x + w - 1, fy + 1, z + d // 2), Block("minecraft:bookshelf"))
        e.placeBlock((x + 1, fy, z + 1), Block("minecraft:potted_azalea_bush"))

    # ------------------------------------------------------------------
    # Forge wing
    # ------------------------------------------------------------------

    def forge_wing(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        wall_h: int,
        forge_d: int,
        work_d: int,
    ) -> None:
        e      = self.e
        work_z = z + forge_d

        # Foundation
        if y - 1 >= -64:
            self._layer(x, y - 1, z, w, d, self.cobble)
        if y - 2 >= -64:
            self._layer(x, y - 2, z, w, d, self.cobble)

        # Stone floor throughout
        self._layer(x, y, z, w, d, self.cobble)

        # ---- Open porch ----
        # Overhead beam across the full south face at porch height
        beam_y = y + wall_h
        for dx in range(w):
            e.placeBlock((x + dx, beam_y, z), Block(self.log))

        # Three log pillars on south face
        for px in (x, x + w // 2, x + w - 1):
            for dy in range(1, wall_h):
                e.placeBlock((px, y + dy, z), Block(self.log))

        # Hanging lanterns on the porch beam
        for lx in (x + 1, x + w - 2):
            place_light(e, (lx, beam_y - 1, z), self.lantern, hanging=True)

        # Side walls of porch section (east + west only, no south)
        for dy in range(1, wall_h + 1):
            for dz in range(1, forge_d):
                e.placeBlock((x,         y + dy, z + dz), Block(self.wall_r))
                e.placeBlock((x + w - 1, y + dy, z + dz), Block(self.wall_r))

        # ---- Enclosed work area ----
        for dy in range(1, wall_h + 1):
            wy  = y + dy
            mid = x + w // 2
            # Back wall
            for dx in range(w):
                e.placeBlock((x + dx, wy, z + d - 1), Block(self.wall_r))
            # Side walls (work section)
            for dz in range(forge_d, d - 1):
                e.placeBlock((x,         wy, z + dz), Block(self.wall_r))
                e.placeBlock((x + w - 1, wy, z + dz), Block(self.wall_r))
            # Partition between porch and work area — leave 1-wide doorway at centre
            for dx in range(w):
                wx = x + dx
                if dx == 0 or dx == w - 1:
                    e.placeBlock((wx, wy, work_z), Block(self.log))
                elif not (wx == mid and dy <= 2):
                    e.placeBlock((wx, wy, work_z), Block(self.wall_r))

        # Back window
        if w >= 5:
            e.placeBlock((x + w // 2, y + 2, z + d - 1), Block(self.window))

        # Gabled roof
        self._roof(x, y + wall_h + 1, z, w, d)

        # Interior equipment
        fy  = y + 1
        cx  = x + w // 2
        iz  = work_z + 1
        e.placeBlock((cx,     fy, iz), Block("minecraft:blast_furnace",
                               {"facing": "south", "lit": "true"}))
        e.placeBlock((cx - 1, fy, iz), Block("minecraft:anvil", {"facing": "west"}))
        e.placeBlock((x + 1,  fy, iz), Block("minecraft:barrel",
                               {"facing": "up", "open": "false"}))
        e.placeBlock((x + w - 2, fy, z + 1),
                     Block("minecraft:grindstone", {"face": "floor", "facing": "north"}))
        if w >= 6:
            e.placeBlock((cx + 1, fy, iz),
                         Block("minecraft:smoker", {"facing": "south", "lit": "false"}))

    # ------------------------------------------------------------------
    # Chimney
    # ------------------------------------------------------------------

    def chimney(
        self,
        cx: int, y: int, z: int,
        d: int,
        left_h: int, right_h: int,
    ) -> None:
        """
        2-block wide cobblestone-to-stone-brick chimney.
        Cobblestone for the lower two-thirds, stone bricks for the top third.
        Campfire on the summit.
        """
        _WORLD_MAX_Y   = 318   # 1 block clearance below hard ceiling
        _CHIMNEY_ABOVE = 10    # blocks above the taller roof peak

        e          = self.e
        roof_peak  = max(left_h, right_h) + max(d // 2, 4)
        top_y      = min(y + roof_peak + _CHIMNEY_ABOVE, _WORLD_MAX_Y)
        trans_y    = y + (top_y - y) * 2 // 3   # cobble → stone brick transition

        cz = z + d // 2
        for iy in range(y, top_y + 1):
            mat = self.cobble if iy <= trans_y else self.stone_br
            e.placeBlock((cx, iy, cz),     Block(mat))
            e.placeBlock((cx, iy, cz + 1), Block(mat))

        # Campfire on summit — only if there is room below the world ceiling
        if top_y + 1 <= _WORLD_MAX_Y:
            e.placeBlock(
                (cx, top_y + 1, cz),
                Block("minecraft:campfire", {"lit": "true", "signal_fire": "false",
                                             "facing": "north"}),
            )

    # ------------------------------------------------------------------
    # Connector (beam + fence gap)
    # ------------------------------------------------------------------

    def connector(
        self,
        x: int, y: int, z: int,
        left_w: int, right_w: int,
        left_h: int, right_h: int,
    ) -> None:
        """
        Oak log beam bridging the chimney column at the lower eave height,
        and a fence-gate section at ground level between the two wings.
        """
        e      = self.e
        beam_y = y + min(left_h, right_h) + 1
        gx     = x + left_w   # chimney column X

        # Connecting beam — two log blocks across the chimney column
        e.placeBlock((gx, beam_y, z + 1), Block(self.log))
        e.placeBlock((gx, beam_y, z + 2), Block(self.log))

        # Ground-level fence with gate in the gap between wings
        for dz in range(1, 4):
            e.placeBlock((gx, y + 1, z + dz), Block(self.fence))
        e.placeBlock((gx, y + 1, z + 2),
                     Block("minecraft:oak_fence_gate",
                           {"facing": "east", "open": "false", "in_wall": "false"}))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _layer(self, x, y, z, w, d, mat):
        positions = [(x + dx, y, z + dz) for dx in range(w) for dz in range(d)]
        self.e.placeBlock(positions, Block(mat))

    def _door(self, door_x, y, face_z, facing):
        self.e.placeBlock(
            (door_x, y + 1, face_z),
            Block(self.door_mat, {"facing": facing, "half": "lower", "hinge": "left"}),
        )
        self.e.placeBlock(
            (door_x, y + 2, face_z),
            Block(self.door_mat, {"facing": facing, "half": "upper", "hinge": "left"}),
        )

    def _roof(self, x, y, z, w, d):
        """Gabled roof with 1-block overhang via the shared roof builder."""
        class _Ctx:
            def __init__(self, editor, palette):
                self.editor  = editor
                self.palette = palette
            def place_block(self, pos, block):
                self.editor.placeBlock(pos, block)

        ctx = _Ctx(self.e, self.p)
        rc  = _RoofCorners(x, y, z, w, d, overhang=1)
        build_gabled_roof(ctx, rc)