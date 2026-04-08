"""Reusable square stone tower builder used by fortification corners and standalone tower plots."""
from __future__ import annotations

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from structures.base.build_context import BuildContext
from world_interface.block_buffer import BlockBuffer
from structures.base.primitives import (
    add_door,
    add_windows,
    build_belfry,
    build_ceiling,
    build_floor,
    build_foundation,
    build_log_belt,
    build_walls,
)
from structures.misc.spire_tower import _build_steep_spire


class TowerBuilder:
    """
    Builds a square stone tower at an absolute world position.

    Stone base (h blocks) → log transition belt → open belfry with arched
    openings → plank platform with hanging lantern → steep tapering spire.

    Args:
        editor:       GDPC editor instance.
        palette:      Biome palette for material lookups.
        height:       Stone base height (blocks y+1 … y+height, plus ceiling
                      at y+height+1).  Default 8.
        width:        Square footprint side length (min 5 for belfry arches).
        with_door:    Place a door on the south face.  Default False.
        with_windows: Place windows on the walls.  Default False.
        rotation:     BuildContext rotation (0 / 90 / 180 / 270).
    """

    def __init__(
        self,
        palette: PaletteSystem,
        height: int = 8,
        width: int = 5,
        with_door: bool = False,
        with_windows: bool = False,
        rotation: int = 0,
    ) -> None:
        self.palette      = palette
        self.height       = height
        self.width        = width
        self.with_door    = with_door
        self.with_windows = with_windows
        self.rotation     = rotation

    def build_at(self, x: int, y: int, z: int) -> BlockBuffer:
        """Place the tower with its bottom-left corner at (x, y, z)."""
        w, h = self.width, self.height

        buffer = BlockBuffer()

        # Plank material from the original palette (before stone override)
        plank_mat = palette_get(self.palette, "wall", "minecraft:dark_oak_planks")
        found_mat = palette_get(self.palette, "foundation", "minecraft:stone_bricks")

        # Stone palette: wall/floor/foundation → stone; ceiling uses lantern
        stone_pal = dict(self.palette)
        stone_pal["wall"]           = found_mat
        stone_pal["floor"]          = found_mat
        stone_pal["foundation"]     = found_mat
        stone_pal["ceiling_slab"]   = "minecraft:stone_brick_slab"
        stone_pal["accent_beam"]    = "minecraft:stripped_dark_oak_log"
        stone_pal["interior_light"] = "minecraft:lantern"

        ctx = BuildContext(buffer, stone_pal, rotation=self.rotation,
                           origin=(x, y, z), size=(w, w))

        # Height milestones (same convention as Tower / SpireTower)
        base_top   = y + h          # ceiling layer
        belt_y     = base_top + 1   # log transition ring
        belfry_h   = 4
        belfry_y   = belt_y + 1     # open belfry starts
        belfry_top = belfry_y + belfry_h  # plank platform
        spire_y    = belfry_top + 1

        with ctx.push():
            build_foundation(ctx, x, y, z, w, w)
            build_floor(ctx,      x, y, z, w, w)
            build_walls(ctx,      x, y, z, w, h, w)
            build_ceiling(ctx,    x, base_top, z, w, w, floor_y=y)

            if self.with_door:
                add_door(ctx, x, y, z, w, facing="south")
            if self.with_windows:
                add_windows(ctx, x, y,     z, w, w)
                add_windows(ctx, x, y + 5, z, w, w)

            build_log_belt(ctx, x, belt_y,  z, w, w)
            build_belfry(  ctx, x, belfry_y, z, w, w, h=belfry_h)

            # Plank platform (uses original-palette "wall" material)
            for dx in range(w):
                for dz in range(w):
                    ctx.place_block((x + dx, belfry_top, z + dz), Block(plank_mat))

            # Hanging lantern from platform centre
            ctx.place_block(
                (x + w // 2, belfry_top - 1, z + w // 2),
                Block("minecraft:lantern", {"hanging": "true"}),
            )

            _build_steep_spire(ctx, x, spire_y, z, w, w)

        return buffer
