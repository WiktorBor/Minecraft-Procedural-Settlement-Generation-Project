"""
structures/misc/fortification.py
----------------------------------
Stone fortification wall with arched openings and a top walkway.

Front face layout:
  [pillar] [arch 3] [pillar] [arch 3] ... [pillar]

Fits as many 3-block arches as the plot width allows, with 1-block stone
pillars between each arch.  The wall is always 5 blocks deep.  A plank
walkway runs along the top.

Minimum plot: 5 wide × 5 deep.
"""
from __future__ import annotations

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from world_interface.block_buffer import BlockBuffer
from structures.base.primitives import (
    build_belfry_face,
    build_floor,
    build_foundation,
    build_walls,
)


class Fortification:
    """
    Stone fortification wall with arched openings.

    As many 3-wide arches as the plot width allows, separated by 1-block
    stone pillars, over a fixed 5-block-deep base.  A plank walkway sits
    on top.

    Minimum plot: 5 wide × 5 deep.
    """

    def build(
        self,
        plot: Plot,
        palette: PaletteSystem,
        rotation: int = 0,
    ) -> BlockBuffer:
        x, y, z = plot.x, plot.y, plot.z
        w       = plot.width

        buffer = BlockBuffer()

        depth  = 5
        wall_h = 6   # blocks y+1 … y+wall_h (6 layers)

        # ----------------------------------------------------------------
        # Arch layout: [pillar][arch3][pillar][arch3]...[pillar]
        # Total width = 1 + n * 4
        # ----------------------------------------------------------------
        n_arches = max(1, (w - 1) // 4)
        fort_w   = 1 + n_arches * 4
        ox       = x + (w - fort_w) // 2   # centre on plot

        # ----------------------------------------------------------------
        # Materials
        # ----------------------------------------------------------------
        wall_mat  = palette_get(palette, "foundation", "minecraft:stone_bricks")
        plank_mat = palette_get(palette, "wall",       "minecraft:dark_oak_planks")
        stair_mat = palette.get("roof",                "minecraft:dark_oak_stairs")
        trap_mat  = "minecraft:dark_oak_trapdoor"

        stone_pal = dict(palette)
        stone_pal["wall"]       = wall_mat
        stone_pal["floor"]      = wall_mat
        stone_pal["foundation"] = wall_mat

        ctx = BuildContext(buffer, stone_pal, rotation=rotation,
                           origin=(ox, y, z), size=(fort_w, depth))

        # Y positions for the arch decoration on the front face
        lintel_y = y + wall_h - 1   # plank lintel row        (y+5)
        arch_y   = y + wall_h - 2   # stair + trap + stair   (y+4)
        open_top = arch_y - 1       # top of open passage     (y+3)

        with ctx.push():
            # Foundation, floor, and perimeter walls
            build_foundation(ctx, ox, y, z, fort_w, depth)
            build_floor(ctx,      ox, y, z, fort_w, depth)
            # build_walls range(1, wall_h+1) → y+1 … y+wall_h
            build_walls(ctx,      ox, y, z, fort_w, wall_h + 1, depth)

            # Top walkway (plank deck)
            walkway_y = y + wall_h + 1
            for dx in range(fort_w):
                for dz in range(depth):
                    ctx.place_block((ox + dx, walkway_y, z + dz), Block(plank_mat))

            # Front face: cut arch openings + place arch decoration
            for i in range(n_arches):
                arch_x = ox + i * 4 + 1

                # Clear the passage (y+1 … open_top inclusive)
                for dx in range(3):
                    for dy in range(1, open_top - y + 1):
                        ctx.place_block((arch_x + dx, y + dy, z),
                                        Block("minecraft:air"))

                # Arch: plank lintel + upside-down stair / trapdoor / stair
                build_belfry_face(
                    ctx, lintel_y, arch_y,
                    along=[(arch_x + dx, z) for dx in range(3)],
                    plank_mat=plank_mat,
                    stair_mat=stair_mat,
                    trap_mat=trap_mat,
                    stair_left ={"facing": "west", "half": "top"},
                    stair_right={"facing": "east", "half": "top"},
                )

        return buffer
