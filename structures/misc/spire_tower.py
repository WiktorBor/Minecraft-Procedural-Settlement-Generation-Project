"""
structures/misc/spire_tower.py
-------------------------------
Tall medieval spire tower with an attached house wing.

Two-part layout along the X axis:
  [Tower (tw wide)] [House Wing (hw wide)]

Tower sections (bottom → top):
  1. Stone brick base  — 10 blocks, arched door + double-height windows
  2. Log transition belt — 1-block accent ring between base and belfry
  3. Open belfry         — 4 blocks of corner log columns + fence arches
  4. Belfry platform     — solid plank deck
  5. Steep spire         — tapering dark-oak stair pyramid + lightning-rod tip

House wing:
  - Gabled roof, chimney, lanterns, internal door connecting to tower

Minimum plot: 10 wide × 6 deep.
"""
from __future__ import annotations

from gdpc import Block
from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.base.primitives import (
    add_chimney,
    add_door,
    add_lanterns,
    add_windows,
    build_belfry,
    build_ceiling,
    build_floor,
    build_foundation,
    build_log_belt,
    build_walls,
)
from structures.roofs.roof_builder import build_roof


class SpireTower:
    """
    Tall medieval spire tower with an attached house wing.

    The tower occupies the left (low-X) portion of the plot: a 10-block
    stone brick base, an open dark-oak belfry, and a steep pyramid spire.
    The house wing fills the remainder with a standard gabled roof.
    An internal connecting door links the two halves.

    Minimum plot: 10 wide × 6 deep.
    """

    def build(
        self,
        editor: Editor,
        plot: Plot,
        palette: BiomePalette,
        rotation: int = 0,
        analysis: WorldAnalysisResult | None = None,
    ) -> None:
        x, y, z = plot.x, plot.y, plot.z
        w, d    = plot.width, plot.depth

        # ----------------------------------------------------------------
        # Sizing
        # ----------------------------------------------------------------
        tw = 5                          # tower footprint width (fixed 3×3)
        td = 5                          # tower footprint depth
        hw = w - tw                    # house wing width
        hx = x + tw                    # house wing X origin

        if hw < 4 or td < 3:
            return

        # ----------------------------------------------------------------
        # Materials
        # ----------------------------------------------------------------
        stone     = palette_get(palette, "foundation", "minecraft:stone_bricks")
        log       = palette_get(palette, "accent",     "minecraft:dark_oak_log")
        plank     = palette_get(palette, "wall",       "minecraft:dark_oak_planks")
        door_id   = palette_get(palette, "door",       "minecraft:spruce_door")

        # Stone palette for the tower base — overrides wall/floor to stone bricks
        stone_pal = dict(palette)
        stone_pal["wall"]           = stone
        stone_pal["floor"]          = stone
        stone_pal["foundation"]     = stone
        stone_pal["ceiling_slab"]   = "minecraft:stone_brick_slab"
        stone_pal["accent_beam"]    = "minecraft:stripped_dark_oak_log"
        stone_pal["interior_light"] = "minecraft:lantern"

        # Both contexts share the same origin + size so rotation pivots match
        ctx       = BuildContext(editor, palette,   rotation=rotation,
                                 origin=(x, y, z),  size=(w, d))
        ctx_stone = BuildContext(editor, stone_pal, rotation=rotation,
                                 origin=(x, y, z),  size=(w, d))

        # Compute how deep each section's foundation must go to always reach
        # the actual terrain under every column of the footprint.
        tower_depth = self._foundation_depth(x, y, z, tw, td, analysis)
        house_depth = self._foundation_depth(hx, y, z, hw, d,  analysis)

        # ----------------------------------------------------------------
        # Height milestones
        # ----------------------------------------------------------------
        stone_h    = 10
        belfry_h   = 4
        base_top   = y + stone_h           # ceiling of stone section (y+10)
        belt_y     = base_top + 1          # transition log ring      (y+11)
        belfry_y   = belt_y + 1            # open belfry starts       (y+12)
        belfry_top = belfry_y + belfry_h   # solid platform above belfry (y+16)
        spire_y    = belfry_top + 1        # spire base               (y+17)

        # ================================================================
        # HOUSE WING
        # ================================================================
        with ctx.push():
            build_foundation(ctx, hx, y,     z, hw, d, depth_below=house_depth)
            build_floor(ctx,      hx, y,     z, hw, d)
            build_walls(ctx,      hx, y,     z, hw, 5, d)
            add_door(ctx,         hx, y,     z, hw, facing="south")
            add_windows(ctx,      hx, y,     z, hw, d)
            build_ceiling(ctx,    hx, y + 5, z, hw, d, floor_y=y)
            build_roof(ctx,       hx, y + 5, z, hw, d, roof_type="gabled")
            add_chimney(ctx,      hx, y,     z, hw, d, building_height=8)
            add_lanterns(ctx,     hx, y,     z, hw, d)

            # Stone entrance step in front of the house door
            step_x = hx + hw // 2
            ctx.place_block((step_x, y, z - 1),
                            Block("minecraft:stone_brick_stairs", {"facing": "north", "half": "bottom"}))

        # ================================================================
        # TOWER — stone base
        # ================================================================
        with ctx_stone.push():
            build_foundation(ctx_stone, x, y,        z, tw, td, depth_below=tower_depth)
            build_floor(ctx_stone,      x, y,        z, tw, td)
            build_walls(ctx_stone,      x, y,        z, tw, stone_h, td)
            add_door(ctx_stone,         x, y,        z, tw, facing="south")
            add_windows(ctx_stone,      x, y,        z, tw, td)          # low windows
            add_windows(ctx_stone,      x, y + 5,    z, tw, td)          # high windows
            build_ceiling(ctx_stone,    x, base_top, z, tw, td, floor_y=y)

            # --- Transition log ring ---
            build_log_belt(ctx_stone, x, belt_y, z, tw, td)

            # --- Open belfry: arched faces ---
            build_belfry(ctx_stone, x, belfry_y, z, tw, td, h=belfry_h)

            # --- Belfry platform (solid dark-oak planks) ---
            for dx in range(tw):
                for dz in range(td):
                    ctx_stone.place_block((x + dx, belfry_top, z + dz), Block(plank))

            # --- Steep spire ---
            _build_steep_spire(ctx_stone, x, spire_y, z, tw, td)

            # --- Internal door: tower east wall → house wing ---
            if hw > 1:
                pass_z = z + td // 2
                # Clear the shared wall passage
                ctx_stone.place_block((x + tw,     y + 1, pass_z), Block("minecraft:air"))
                ctx_stone.place_block((x + tw,     y + 2, pass_z), Block("minecraft:air"))
                # Step on house-wing side
                ctx_stone.place_block((x + tw + 1, y,     pass_z), Block(stone))
                # Door on tower east wall
                ctx_stone.place_block(
                    (x + tw - 1, y + 1, pass_z),
                    Block(door_id, {"facing": "east", "half": "lower", "hinge": "left"}),
                )
                ctx_stone.place_block(
                    (x + tw - 1, y + 2, pass_z),
                    Block(door_id, {"facing": "east", "half": "upper", "hinge": "left"}),
                )


    @staticmethod
    def _foundation_depth(
        x: int, y: int, z: int,
        w: int, d: int,
        analysis: WorldAnalysisResult | None,
        fallback: int = 15,
    ) -> int:
        """
        Return how many blocks below ``y`` the foundation must extend to
        reach the lowest terrain point under every column of the footprint.

        If ``analysis`` is available the heightmap is sampled at every (x, z)
        column; otherwise ``fallback`` is returned.
        """
        if analysis is None:
            return fallback

        area   = analysis.best_area
        hmap   = analysis.heightmap_ground
        min_gy = y   # start at plot level; only go deeper as needed

        for dx in range(w):
            for dz in range(d):
                try:
                    li, lj = area.world_to_index(x + dx, z + dz)
                except ValueError:
                    continue
                gy = int(hmap[li, lj])
                if gy < min_gy:
                    min_gy = gy

        # depth = how far below y the lowest ground column sits, plus 1 for solid contact
        return max(1, y - min_gy + 1)


# ---------------------------------------------------------------------------
# Steep spire — module-level helper
# ---------------------------------------------------------------------------

def _build_steep_spire(
    ctx: BuildContext,
    x: int, y: int, z: int,
    w: int, d: int,
) -> None:
    """
    Steep tapered spire starting from (x, y, z) over a w×d footprint.

    Reduces the perimeter ring by 1 on every side each layer, beginning with
    a 1-block eave overhang.  Finishes with a stone-brick cap, iron bars, and
    a lightning rod.
    """
    mat_stair = ctx.palette.get("roof",       "minecraft:dark_oak_stairs")
    mat_full  = palette_get(ctx.palette, "roof_block", "minecraft:dark_oak_planks")

    x0, x1 = x - 1, x + w      # start 1 block outside footprint (eave)
    z0, z1 = z - 1, z + d
    cur_y  = y

    while x0 < x1 and z0 < z1:
        # South row
        for lx in range(x0, x1 + 1):
            ctx.place_block((lx, cur_y, z0), Block(mat_stair, {"facing": "south"}))
        # North row
        for lx in range(x0, x1 + 1):
            ctx.place_block((lx, cur_y, z1), Block(mat_stair, {"facing": "north"}))
        # West column (skip corners already placed)
        for lz in range(z0 + 1, z1):
            ctx.place_block((x0, cur_y, lz), Block(mat_stair, {"facing": "east"}))
        # East column
        for lz in range(z0 + 1, z1):
            ctx.place_block((x1, cur_y, lz), Block(mat_stair, {"facing": "west"}))

        x0 += 1;  x1 -= 1
        z0 += 1;  z1 -= 1
        cur_y += 1

    # Converged to a single point or a 1-wide row — full block cap
    for lx in range(x0, x1 + 1):
        for lz in range(z0, z1 + 1):
            ctx.place_block((lx, cur_y, lz), Block(mat_full))
    cur_y += 1

    # Tip: stone block + banner
    cx = x + w // 2
    cz = z + d // 2
    banner = palette_get(ctx.palette, "banner", "minecraft:white_banner")
    ctx.place_block((cx, cur_y,     cz), Block("minecraft:stone_bricks"))
    ctx.place_block((cx, cur_y + 1, cz), Block(banner, {"rotation": "0"}))
