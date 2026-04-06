"""
structures/misc/clock_tower.py
--------------------------------
Medieval clock tower with a stone base, clock housing, and spire.

Uses direct editor calls — adapted from ClockTowerTemplate to use
BiomePalette keys and the project's Plot convention.
"""
from __future__ import annotations

from gdpc import Block

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot

from structures.base.build_context import BuildContext
from world_interface.block_buffer import BlockBuffer
from structures.base.primitives import (
    add_door,
    build_ceiling,
    build_floor,
    build_foundation,
    build_walls,
)
from structures.roofs.roof_builder import build_roof


class ClockTower:
    """
    Four-tier clock tower:
      1. Stone base with arched door (10 blocks tall)
      2. Clock housing with wood corners and bone-block clock faces (8 blocks)
      3. Steep pyramid roof
      4. Iron-bar + lightning-rod spire
    """

    def build(
        self,
        _editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
    ) -> BlockBuffer:
        y  = plot.y
        cx = plot.x + plot.width  // 2
        cz = plot.z + plot.depth  // 2
        r  = min(plot.width, plot.depth, 7) // 2
        tw = r * 2 + 1   # tower footprint (square, centred on cx/cz)
        ox = cx - r      # top-left corner X
        oz = cz - r      # top-left corner Z

        log = palette_get(palette, "accent", "minecraft:dark_oak_log")

        buffer = BlockBuffer()
        ctx = BuildContext(buffer, palette, rotation=rotation,
                           origin=(ox, y, oz), size=(tw, tw))

        with ctx.push():
            # Foundation — drives 3 blocks into terrain
            build_foundation(ctx, ox, y, oz, tw, tw)

            # --- Tier 1: Stone base (10 blocks tall) ---
            build_floor(ctx,  ox, y,      oz, tw, tw)
            build_walls(ctx,  ox, y,      oz, tw, 10, tw)
            add_door(ctx,     ox, y,      oz, tw, facing="south")

            # --- Transition band: accent log ring between base and housing ---
            housing_y = y + 10
            for dcx in range(tw):
                for dcz in range(tw):
                    if dcx == 0 or dcx == tw - 1 or dcz == 0 or dcz == tw - 1:
                        ctx.place_block((ox + dcx, housing_y, oz + dcz), Block(log))

            # --- Tier 2: Clock housing (8 blocks tall) ---
            housing_y += 1
            build_floor(ctx,  ox, housing_y,     oz, tw, tw)
            build_walls(ctx,  ox, housing_y,     oz, tw, 8,  tw)

            # Overwrite corners with accent log
            for dy in range(1, 8):
                for dcx, dcz in [(-r, -r), (r, -r), (-r, r), (r, r)]:
                    ctx.place_block((cx + dcx, housing_y + dy, cz + dcz), Block(log))

            # Ceiling with hanging lantern
            ceiling_y = housing_y + 8
            build_ceiling(ctx, ox, ceiling_y, oz, tw, tw, floor_y=housing_y)

            # Clock faces on all 4 sides (bone block 3×3 + gold centre)
            face_y = housing_y + 3
            for fdx, fdz in [(0, -r), (0, r), (r, 0), (-r, 0)]:
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        px = cx + (dx if fdz != 0 else fdx)
                        py = face_y + dy
                        pz = cz + (fdz if fdz != 0 else dx)
                        ctx.place_block((px, py, pz), Block("minecraft:bone_block"))
                ctx.place_block((cx + fdx, face_y, cz + fdz), Block("minecraft:gold_block"))

            # --- Tier 3: Pyramid roof ---
            roof_y = ceiling_y + 1
            build_roof(ctx, ox, roof_y, oz, tw, tw, roof_type="pyramid")

            # --- Tier 4: Spire ---
            apex_y = roof_y + r + 2
            ctx.place_block((cx, apex_y,     cz), Block("minecraft:stone_bricks"))
            ctx.place_block((cx, apex_y + 1, cz), Block("minecraft:iron_bars"))
            ctx.place_block((cx, apex_y + 2, cz), Block("minecraft:lightning_rod"))

        return buffer
