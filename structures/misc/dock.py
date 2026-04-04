"""
structures/misc/dock.py
------------------------
Wooden fishing dock: oak-plank deck, dark-oak log pillars, cobblestone
bollards, oak fence railings, and lanterns.

Layout (rotation 0, front faces south toward water):

    ████████████████   ← main deck (full width, ~60 % of depth)
    ████████████████
    ████████████████
         ██████        ← finger pier (centred, ~⅓ width, remaining depth)
         ██████
         ██████        tip (open, fishing end)

Pillars descend _PILLAR_DEPTH blocks below the deck surface at every
corner and on a regular grid.  Cobblestone bollards cap each pillar one
block above the deck.  Oak fence rails run around all exposed edges.
Lanterns sit on the main-deck corners and hang over the pier tip.
"""
from __future__ import annotations

import logging

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext

logger = logging.getLogger(__name__)

_PILLAR_DEPTH = 4   # blocks the pillar extends below deck level
_BOLLARD_H    = 1   # blocks the cobblestone cap rises above deck


def water_facing_rotation(
    cx: int,
    cz: int,
    area,
    water_mask,
    max_range: int = 30,
) -> int:
    """
    Return the rotation (0/90/180/270) whose forward direction (+Z before
    rotation) points toward the nearest water cell from (cx, cz).

    Falls back to 0 (south) when no water is found within ``max_range``.
    """
    # (dx, dz, rotation) — rotation so the dock pier faces this direction
    directions = [
        ( 0,  1,   0),   # south  → rotation 0
        ( 0, -1, 180),   # north  → rotation 180
        (-1,  0,  90),   # west   → rotation 90
        ( 1,  0, 270),   # east   → rotation 270
    ]
    best_rot  = 0
    best_dist = max_range + 1

    for dx, dz, rot in directions:
        for step in range(1, max_range + 1):
            try:
                li, lj = area.world_to_index(cx + dx * step, cz + dz * step)
            except ValueError:
                break
            if water_mask[li, lj]:
                if step < best_dist:
                    best_dist = step
                    best_rot  = rot
                break

    return best_rot


class Dock:
    """
    Fishing dock placed at the centre of a fishing district.

    The front of the dock (finger pier tip) faces toward water; pass
    ``rotation`` to orient correctly (south=0, west=90, north=180, east=270).
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

        # Override palette with dock-specific materials
        dock_pal                    = dict(palette)
        dock_pal["floor"]           = "minecraft:oak_planks"
        dock_pal["foundation"]      = "minecraft:dark_oak_log"
        dock_pal["accent"]          = "minecraft:cobblestone"
        dock_pal["light"]           = palette_get(palette, "light", "minecraft:lantern")

        ctx = BuildContext(editor, dock_pal, rotation=rotation,
                           origin=(x, y, z), size=(w, d))

        # --- Dimension split -------------------------------------------------
        # Main deck  : full-width rectangle at the back (land side)
        # Finger pier: narrower rectangle extending forward (water side)
        main_d = max(3, (d * 3) // 5)
        pier_d = d - main_d
        pier_w = max(3, w // 3)
        pier_ox = (w - pier_w) // 2   # local X offset of pier within the plot

        logger.debug(
            "Dock at (%d,%d) y=%d  plot=%dx%d  main_d=%d  pier=%dx%d  pier_ox=%d",
            x, z, y, w, d, main_d, pier_w, pier_d, pier_ox,
        )

        with ctx.push():
            # 1. Deck surfaces (planks)
            self._fill(ctx, x, y, z, w, main_d)
            if pier_d >= 2:
                self._fill(ctx, x + pier_ox, y, z + main_d, pier_w, pier_d)

            # 2. Log pillars + cobblestone bollards on a grid
            pillar_pts: set[tuple[int, int]] = set()
            pillar_pts.update(self._grid(x,          z,          w,      main_d))
            if pier_d >= 2:
                pillar_pts.update(self._grid(x + pier_ox, z + main_d, pier_w, pier_d))

            for px, pz in pillar_pts:
                self._pillar(ctx, px, y, pz)
                self._bollard(ctx, px, y, pz)

            # 3. Fence railings
            #    Main deck: fence on all 4 sides, but leave the pier opening
            #    on the front edge so the two sections connect visually.
            gap = (pier_ox, pier_ox + pier_w - 1)   # local dx gap on front row
            self._fence_rect(ctx, x, y, z, w, main_d, front_gap=gap)
            if pier_d >= 2:
                # Pier: fence on left, right and tip only (no back — opens to main deck)
                self._fence_rect(ctx, x + pier_ox, y, z + main_d, pier_w, pier_d,
                                 skip_back=True)

            # 4. Lanterns on the four main-deck corners + pier tip corners
            light_y = y + _BOLLARD_H + 1
            corner_lights = [
                (x,                          z),
                (x + w - 1,                  z),
                (x + pier_ox,                z + d - 1),
                (x + pier_ox + pier_w - 1,   z + d - 1),
            ]
            for px, pz in corner_lights:
                ctx.place_light((px, light_y, pz), key="light", hanging=False)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fill(ctx: BuildContext, x: int, y: int, z: int, w: int, d: int) -> None:
        """Oak-plank deck rectangle."""
        ctx.place_many(
            [(x + dx, y, z + dz) for dx in range(w) for dz in range(d)],
            "floor",
        )

    @staticmethod
    def _grid(x: int, z: int, w: int, d: int, step: int = 3) -> list[tuple[int, int]]:
        """
        Return (world_x, world_z) pillar positions at every corner plus
        every `step` blocks along all four edges of the rectangle.
        """
        pts: set[tuple[int, int]] = set()
        for dx in range(0, w, step):
            pts.add((x + dx, z))
            pts.add((x + dx, z + d - 1))
        pts.add((x + w - 1, z))
        pts.add((x + w - 1, z + d - 1))
        for dz in range(0, d, step):
            pts.add((x,         z + dz))
            pts.add((x + w - 1, z + dz))
        return list(pts)

    @staticmethod
    def _pillar(ctx: BuildContext, x: int, y: int, z: int) -> None:
        """Dark-oak log column from y-1 down to y-_PILLAR_DEPTH."""
        ctx.place_many(
            [(x, y - dy, z) for dy in range(1, _PILLAR_DEPTH + 1)],
            "foundation",
        )

    @staticmethod
    def _bollard(ctx: BuildContext, x: int, y: int, z: int) -> None:
        """Cobblestone cap rising _BOLLARD_H blocks above the deck."""
        ctx.place_many(
            [(x, y + dy, z) for dy in range(1, _BOLLARD_H + 1)],
            "accent",
        )

    @staticmethod
    def _fence_rect(
        ctx: BuildContext,
        x: int, y: int, z: int,
        w: int, d: int,
        front_gap: tuple[int, int] | None = None,
        skip_back: bool = False,
    ) -> None:
        """
        Oak fence perimeter around a rectangle.

        front_gap  : (dx_min, dx_max) local-X range to leave open on the
                     front (z + d - 1) edge — used to connect main deck to pier.
        skip_back  : omit the back (z) edge — used on the pier so it opens
                     flush into the main deck.
        """
        fence  = "minecraft:oak_fence"
        rail_y = y + 1

        # Back edge
        if not skip_back:
            for dx in range(w):
                ctx.place_block((x + dx, rail_y, z), Block(fence))

        # Left and right edges
        for dz in range(d):
            ctx.place_block((x,         rail_y, z + dz), Block(fence))
            ctx.place_block((x + w - 1, rail_y, z + dz), Block(fence))

        # Front edge (optional pier gap)
        for dx in range(w):
            if front_gap and front_gap[0] <= dx <= front_gap[1]:
                continue
            ctx.place_block((x + dx, rail_y, z + d - 1), Block(fence))
