"""
structures/misc/tavern.py
--------------------------
Medieval tavern complex: elevated tavern body + covered bridge + stone tower.

Three-part layout along the X axis (all sharing depth d):
  [  Tavern (tw)  ] [ Bridge (bw) ] [ Tower (gw) ]

Minimum plot: 20 wide × 12 deep.
"""
from __future__ import annotations

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.base.primitives import (
    add_door,
    add_lanterns,
    add_windows,
    build_ceiling,
    build_floor,
    build_foundation,
    build_walls,
)
from structures.roofs.roof_builder import build_roof


class Tavern:
    """
    Three-part tavern complex:
      1. Elevated tavern with half-timbered walls and gabled roof
      2. Covered bridge connecting tavern to tower
      3. Stone tower with pyramid roof
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

        # Partition width: tavern ~50%, bridge ~20%, tower ~30%
        tw = max(7,  int(w * 0.50))
        bw = max(3,  int(w * 0.20))
        gw = w - tw - bw

        if gw < 4:
            return

        wall_mat = palette_get(palette, "wall",       "minecraft:white_terracotta")
        frame    = palette_get(palette, "accent",     "minecraft:spruce_log")
        door_mat = palette_get(palette, "door",       "minecraft:spruce_door")
        fence    = palette_get(palette, "fence",      "minecraft:spruce_fence")
        light    = palette_get(palette, "light",      "minecraft:lantern")
        path_mat = palette_get(palette, "path",       "minecraft:stone_bricks")

        stilt_h  = 3
        wall_h   = 6
        tower_h  = 12

        # ----------------------------------------------------------------
        # PART 1: Elevated tavern
        # ----------------------------------------------------------------
        ctx_t = BuildContext(editor, palette, rotation=rotation,
                             origin=(x, y, z), size=(tw, d))
        with ctx_t.push():
            # Stilts at four corners
            for sy in range(stilt_h):
                for sx, sz in [(1, 1), (1, d - 2), (tw - 2, 1), (tw - 2, d - 2)]:
                    ctx_t.place_block((x + sx, y + sy, z + sz), Block(frame))

            ty = y + stilt_h
            build_foundation(ctx_t, x, ty, z, tw, d)
            build_floor(ctx_t,      x, ty, z, tw, d)
            build_walls(ctx_t,      x, ty, z, tw, wall_h, d)

            # Half-timbered frame: overwrite wall posts with accent log
            for dy in range(1, wall_h):
                for dx in range(0, tw, max(2, tw // 3)):
                    ctx_t.place_block((x + dx, ty + dy, z),         Block(frame))
                    ctx_t.place_block((x + dx, ty + dy, z + d - 1), Block(frame))
                for dz in range(0, d, max(2, d // 3)):
                    ctx_t.place_block((x,           ty + dy, z + dz), Block(frame))
                    ctx_t.place_block((x + tw - 1,  ty + dy, z + dz), Block(frame))

            add_door(ctx_t,    x, ty, z, tw, facing="south")
            add_windows(ctx_t, x, ty, z, tw, d)
            build_ceiling(ctx_t, x, ty + wall_h, z, tw, d, floor_y=ty)
            build_roof(ctx_t,  x, ty + wall_h + 1, z, tw, d, roof_type="gabled")
            add_lanterns(ctx_t, x, ty, z, tw, d)

        # ----------------------------------------------------------------
        # PART 2: Covered bridge
        # ----------------------------------------------------------------
        bx   = x + tw
        b_h  = 3
        ctx_b = BuildContext(editor, palette, rotation=rotation,
                             origin=(bx, y, z), size=(bw, d))
        with ctx_b.push():
            # Stone path at ground level
            for dx in range(bw):
                for dz in range(d):
                    ctx_b.place_block((bx + dx, y, z + dz), Block(path_mat))

            # Raised bridge floor + side walls
            ty2 = y + stilt_h
            for dx in range(bw):
                for dz in range(d):
                    ctx_b.place_block((bx + dx, ty2, z + dz), Block(path_mat))
                for dz in range(1, b_h + 1):
                    ctx_b.place_block((bx + dx, ty2 + dz, z),         Block(wall_mat))
                    ctx_b.place_block((bx + dx, ty2 + dz, z + d - 1), Block(wall_mat))
                # Slab roof over the bridge
                ctx_b.place_block((bx + dx, ty2 + b_h + 1, z + d // 2), Block(
                    palette_get(palette, "roof_slab", "minecraft:dark_oak_slab")
                ))

        # ----------------------------------------------------------------
        # PART 3: Stone tower
        # ----------------------------------------------------------------
        gx    = x + tw + bw
        ctx_g = BuildContext(editor, palette, rotation=rotation,
                             origin=(gx, y, z), size=(gw, d))

        # Swap wall to stone for the tower
        stone_palette = dict(palette)
        stone_palette["wall"]       = palette_get(palette, "foundation", "minecraft:stone_bricks")
        stone_palette["foundation"] = palette_get(palette, "foundation", "minecraft:stone_bricks")

        ctx_g = BuildContext(editor, stone_palette, rotation=rotation,
                             origin=(gx, y, z), size=(gw, d))
        with ctx_g.push():
            build_foundation(ctx_g, gx, y, z, gw, d)
            build_floor(ctx_g,      gx, y, z, gw, d)
            build_walls(ctx_g,      gx, y, z, gw, tower_h, d)
            add_door(ctx_g,         gx, y, z, gw, facing="south")
            add_windows(ctx_g,      gx, y + 4, z, gw, d)
            build_ceiling(ctx_g,    gx, y + tower_h, z, gw, d, floor_y=y)
            build_roof(ctx_g,       gx, y + tower_h + 1, z, gw, d, roof_type="pyramid")

        # Fence post + lantern in front of bridge entrance
        lx = bx + bw // 2
        editor.placeBlock((lx, y + 1, z - 1), Block(fence))
        editor.placeBlock((lx, y + 2, z - 1), Block(light))
