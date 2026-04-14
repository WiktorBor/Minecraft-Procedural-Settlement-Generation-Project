"""
terraforming.py
---------------
Terrain modification operations for the settlement generation pipeline.

terraform_area operates in two modes depending on whether plots are supplied:

  **Smooth mode** (no plots):
      Iterative neighbourhood averaging that shaves bumps downward.
      Used by settlement_generator in Phase 2 before plot planning.

  **Platform mode** (plots provided):
      Additive-only fill — raises terrain to min(plot.y) so structures
      have a solid base. Optionally blends outward beyond best_area.

Public API
----------
terraform_area(editor, analysis, plots=None, ...)
    Dual-mode: smooth downward when plots=None, platform fill otherwise.

terraform_perimeter(editor, analysis, config, ...)
    Level the perimeter band so the fortification wall sits on flat ground.

fill_depressions(editor, analysis, ...)
    Detect and fill terrain depressions (replaces fill_all_holes + seal_cave_openings).

remove_sparse_top(editor, analysis, ...)
    Remove sparse terrain clusters above the dominant flat level.

clear_area(editor, analysis, plot, config)
    Clear vegetation in a circular area around a plot.

level_plot_area(editor, analysis, plot, ...)
    Level the terrain under a single plot footprint to its median height.

fill_below_surface(editor, analysis, target_height, ...)
    Fill all cells below target_height using sampled neighbouring blocks.

clear_lava_pools(editor, analysis)
    Clear surface lava pools and fill them flush with the surrounding terrain.

recompute_all_maps(editor, analysis, config)
    Recompute all derived terrain maps after any terraforming operations.

Call order in settlement_generator.py Phase 2
----------------------------------------------
    remove_sparse_top(...)    # smooth terrain clusters
    terraform_area(...)       # smooth bumps downward (no plots)
    recompute_all_maps(...)   # refresh slope/roughness for planners
"""
from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

import numpy as np
from gdpc import Block
from gdpc.editor import Editor
from gdpc.vector_tools import Rect
from scipy.ndimage import (
    binary_closing,
    label as ndimage_label,
    uniform_filter,
    distance_transform_edt
)

from data.analysis_results import WorldAnalysisResult
from data.build_area import BuildArea
from data.configurations import SettlementConfig, TerrainConfig
from data.settlement_entities import Districts, Plot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FILL_OVER: frozenset[str] = frozenset({
    "minecraft:water",
    "minecraft:flowing_water",
    "minecraft:lily_pad",
})

# Natural terrain block IDs — only these are safe to remove.
_NATURAL_BLOCKS: frozenset[str] = frozenset({
    "minecraft:grass_block", "minecraft:dirt", "minecraft:coarse_dirt",
    "minecraft:podzol", "minecraft:rooted_dirt", "minecraft:mud",
    "minecraft:stone", "minecraft:deepslate", "minecraft:cobblestone",
    "minecraft:mossy_cobblestone", "minecraft:gravel", "minecraft:sand",
    "minecraft:red_sand", "minecraft:sandstone", "minecraft:red_sandstone",
    "minecraft:clay", "minecraft:packed_ice", "minecraft:snow_block",
    "minecraft:ice", "minecraft:netherrack", "minecraft:soul_sand",
    "minecraft:soul_soil", "minecraft:basalt", "minecraft:blackstone",
    "minecraft:mycelium", "minecraft:grass", "minecraft:tall_grass",
    "minecraft:water", "minecraft:lava",
})

_EMPTY_LIKE_IDS: frozenset[str] = frozenset({
    "minecraft:water",
    "minecraft:lava",
    "minecraft:tall_grass",
    "minecraft:grass",
    "minecraft:fern",
    "minecraft:large_fern",
    "minecraft:vine",
    "minecraft:seagrass",
    "minecraft:tall_seagrass",
    "minecraft:kelp",
    "minecraft:snow",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_natural(block_id: str) -> bool:
    bid = block_id.lower()
    return bid in _NATURAL_BLOCKS or any(
        bid.endswith(suffix) for suffix in (
            "_ore", "_stone", "_dirt", "_sand", "_gravel",
            "_leaves", "_log", "_wood", "_sapling",
        )
    )


def _is_empty_like(block_id: str) -> bool:
    """Return True for air, fluid, and plant-type blocks (safe to overwrite)."""
    bid = block_id.lower()
    if "air" in bid:
        return True
    if bid in _EMPTY_LIKE_IDS:
        return True
    return ("flower" in bid) or ("leaves" in bid)


def _fill_vertical_column(
    editor: Editor,
    x: int,
    z: int,
    y_lo: int,
    y_hi: int,
    block_type: str,
    *,
    use_fill_command: bool,
) -> None:
    """Place blocks from y_lo to y_hi inclusive."""
    if y_lo > y_hi:
        return
    if use_fill_command and hasattr(editor, "runCommandGlobal"):
        editor.runCommandGlobal(f"fill {x} {y_lo} {z} {x} {y_hi} {z} {block_type}")
        return
    positions = [(x, y, z) for y in range(y_lo, y_hi + 1)]
    editor.placeBlock(positions, Block(block_type))


def iter_moat_perimeter_cells(
    area: BuildArea,
    tower_width: int,
    wall_thickness: int,
    extra: int = 2,
) -> Iterator[tuple[int, int]]:
    """
    Yield world XZ cells outside best_area that lie in the fortification
    "moat" band (settlement edge to wall midline + thickness).
    """
    mid = tower_width // 2
    reach = mid + wall_thickness + max(1, extra)
    bands = (
        (area.x_from - reach, area.x_to + reach, area.z_from - reach, area.z_from - 1),
        (area.x_from - reach, area.x_to + reach, area.z_to + 1, area.z_to + reach),
        (area.x_from - reach, area.x_from - 1, area.z_from - reach, area.z_to + reach),
        (area.x_to + 1, area.x_to + reach, area.z_from - reach, area.z_to + reach),
    )
    seen: set[tuple[int, int]] = set()
    for x0, x1, z0, z1 in bands:
        for x in range(int(x0), int(x1) + 1):
            for z in range(int(z0), int(z1) + 1):
                if area.x_from <= x <= area.x_to and area.z_from <= z <= area.z_to:
                    continue
                key = (x, z)
                if key in seen:
                    continue
                seen.add(key)
                yield x, z


def bridge_void_under_floor(
    editor: Editor,
    x: int,
    z: int,
    floor_y: int,
    min_y: int,
    block_type: str,
    *,
    use_fill_command: bool,
) -> bool:
    """
    Fill any vertical run of empty/fluid blocks directly under a floor.
    Returns True if any fill was applied.
    """
    if not hasattr(editor, "getBlock"):
        return False
    top = floor_y - 1
    y = top
    while y >= min_y:
        bid = getattr(editor.getBlock((x, y, z)), "id", "minecraft:air")
        if not _is_empty_like(bid):
            break
        y -= 1
    fill_bottom = y + 1
    if fill_bottom > top:
        return False
    _fill_vertical_column(
        editor, x, z, fill_bottom, top, block_type,
        use_fill_command=use_fill_command,
    )
    return True


def _modal_y(heightmap: np.ndarray) -> int:
    """Most common Y value across a heightmap array."""
    values, counts = np.unique(heightmap, return_counts=True)
    return int(values[np.argmax(counts)])


def _fill_sinks(
    heightmap: np.ndarray,
    threshold: int = 1,
) -> np.ndarray:
    """
    Fill local pits and holes by raising each cell to the minimum of its
    8-neighbours when it is more than `threshold` blocks below them.

    This handles open Minecraft holes, ravines, and cave entrances that are
    NOT enclosed basins (and therefore not caught by priority-flood).  Each
    pit cell is filled just enough to meet its lowest surrounding neighbour,
    preserving slopes and hills completely.

    Iterates until stable (typically 2-4 passes for most terrain).
    """
    from scipy.ndimage import minimum_filter

    result = heightmap.astype(np.int32).copy()

    # Footprint that excludes the center cell so neighbour_min reflects only
    # the 8 surrounding cells.  Using size=3 would include the center, making
    # neighbour_min <= result always — the pit_mask would never fire.
    footprint = np.ones((3, 3), dtype=bool)
    footprint[1, 1] = False

    for _ in range(20):  # max passes — converges well before this
        # Minimum of the 8 surrounding neighbours (center excluded)
        neighbour_min = minimum_filter(result, footprint=footprint, mode="nearest")
        # A cell is a pit if it's below its lowest neighbour by > threshold
        pit_mask = result < (neighbour_min - threshold)
        if not pit_mask.any():
            break
        # Raise pit cells to their lowest neighbour
        result[pit_mask] = neighbour_min[pit_mask]

    return result


def _fill_rect(
    editor:     Editor,
    world_rect: Rect,
    heightmap:  np.ndarray,
    target_y:   int,
    fill_block: str = "minecraft:dirt",
    top_block:  str = "minecraft:grass_block",
    slope_width: int = 3,
) -> None:
    """
    Seal the depression by placing a flat horizontal cap at target_y across
    every column in world_rect that is below target_y (XZ-plane seal).

    For each column:
      - If already at or above target_y: skip (never carve).
      - If below target_y: place fill_block from actual_surface+1 to target_y-1,
        then place top_block at target_y as the visible surface cap.
      - Water columns (fountains etc.) are filled over.

    Updates heightmap in-place.
    """
    w  = world_rect.size.x
    d  = world_rect.size.y
    ox = world_rect.offset.x
    oz = world_rect.offset.y
    done = skipped = 0

    for dx in range(w):
        for dz in range(d):
            wx = ox + dx
            wz = oz + dz
            surf = int(heightmap[dx, dz])

            # Walk down past any water to find the true solid surface
            actual_surf = surf
            for y in range(surf, surf - 10, -1):
                if editor.getBlock((wx, y, wz)).id in _FILL_OVER:
                    actual_surf = y - 1
                else:
                    break

            # Never carve down
            if actual_surf >= target_y:
                skipped += 1
                continue

            # Fill subsurface columns with dirt
            for y in range(actual_surf + 1, target_y):
                editor.placeBlock((wx, y, wz), Block(fill_block))

            # Place the flat surface cap at target_y
            editor.placeBlock((wx, target_y, wz), Block(top_block))

            heightmap[dx, dz] = target_y
            done += 1

    logger.info(
        "_fill_rect: %d columns sealed at Y=%d (XZ plane), %d skipped.",
        done, target_y, skipped,
    )


def _fill_component(
    editor:      Editor,
    cells:       np.ndarray,
    heightmap:   np.ndarray,
    search_offset_x: int,
    search_offset_z: int,
    target_y:    int,
    fill_block:  str = "minecraft:dirt",
    top_block:   str = "minecraft:grass_block",
) -> int:
    """
    Fill the depression component and all connected cells below target_y.

    Starting from the flagged depression cells, a BFS flood-fills outward:
    any 4-connected neighbour that is also below target_y is pulled into the
    fill set.  This ensures the fill meets existing grass at every edge so no
    exposed stone/dirt walls are left at the sides of the hole.

    Parameters
    ----------
    cells          : (N, 2) array of local heightmap indices (from ndimage_label)
    heightmap      : full search-area heightmap (surface block Y, GDPC -1 convention)
    search_offset_x: world X of heightmap[0,0]
    search_offset_z: world Z of heightmap[0,0]
    target_y       : fill target (surface block Y)

    Returns the number of columns filled.
    """
    h, d = heightmap.shape

    # Flood-fill: start from depression cells, expand to all connected cells
    # that are still below target_y.
    to_fill: set[tuple[int, int]] = {(int(r), int(c)) for r, c in cells}
    queue   = list(to_fill)
    head    = 0

    while head < len(queue):
        li, lj = queue[head]; head += 1
        for dli, dlj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ni, nj = li + dli, lj + dlj
            if not (0 <= ni < h and 0 <= nj < d):
                continue
            if (ni, nj) in to_fill:
                continue
            if int(heightmap[ni, nj]) < target_y:
                to_fill.add((ni, nj))
                queue.append((ni, nj))

    done = 0
    for li, lj in to_fill:
        wx   = search_offset_x + li
        wz   = search_offset_z + lj
        surf = int(heightmap[li, lj])

        if surf >= target_y:
            continue  # already at or above target — never carve

        for y in range(surf + 1, target_y):
            editor.placeBlock((wx, y, wz), Block(fill_block))
        editor.placeBlock((wx, target_y, wz), Block(top_block))

        heightmap[li, lj] = target_y
        done += 1

    return done


# ---------------------------------------------------------------------------
# terraform_area  (dual mode)
# ---------------------------------------------------------------------------

def terraform_area(
    editor:              Editor,
    analysis:            WorldAnalysisResult,
    # ---- platform mode (additive) ----
    plots:               list[Plot] | None = None,
    exclude_plots:       list[Plot] | None = None,
    allowed_mask:        np.ndarray | None = None,
    fill_width:          int | None = None,
    fill_depth:          int | None = None,
    fill_moat_perimeter: bool = False,
    moat_extra:          int = 2,
    fill_plot_support:   bool = False,
    fill_area:           bool = True,
    use_world_scan:      bool = False,
    max_scan_depth:      int | None = 24,
    connect_fill_gaps:   bool = True,
    outer_blend_width:   int = 0,
    use_fill_command:    bool = True,
    block_type:          str = "minecraft:grass_block",
    # ---- smooth mode (downward) ----
    passes:              int   = 3,
    smooth_radius:       int   = 3,
    max_change_per_pass: float = 1.0,
    **kwargs: Any,
) -> None:
    """
    Dual-mode terrain modification.

    **Smooth mode** (``plots`` is None or empty):
        Iterative downward neighbourhood averaging — shaves bumps without
        raising anything.

    **Platform mode** (``plots`` provided):
        Additive-only fill.  Raises every allowed column inside best_area
        to ``target_y = min(plot.y)``.
    """
    del kwargs

    if plots:
        _terraform_platform(
            editor=editor,
            analysis=analysis,
            plots=plots,
            exclude_plots=exclude_plots,
            allowed_mask=allowed_mask,
            fill_width=fill_width,
            fill_depth=fill_depth,
            fill_moat_perimeter=fill_moat_perimeter,
            moat_extra=moat_extra,
            fill_plot_support=fill_plot_support,
            fill_area=fill_area,
            use_world_scan=use_world_scan,
            max_scan_depth=max_scan_depth,
            connect_fill_gaps=connect_fill_gaps,
            outer_blend_width=outer_blend_width,
            use_fill_command=use_fill_command,
            block_type=block_type,
        )
    else:
        _terraform_smooth(
            editor=editor,
            analysis=analysis,
            passes=passes,
            smooth_radius=smooth_radius,
            max_change_per_pass=max_change_per_pass,
        )


def _terraform_smooth(
    editor:              Editor,
    analysis:            WorldAnalysisResult,
    passes:              int   = 3,
    smooth_radius:       int   = 3,
    max_change_per_pass: float = 1.0,
    min_shave_blocks:    float = 1.5,
) -> None:
    """
    Smooth terrain bumps using iterative neighbourhood averaging (downward only).
    """
    area           = analysis.best_area
    heightmap      = analysis.heightmap_ground.astype(np.float32)
    w, d           = heightmap.shape
    size           = 2 * smooth_radius + 1
    surface_blocks = analysis.surface_blocks

    snow_mask = np.vectorize(
        lambda b: "snow" in str(b).lower()
    )(surface_blocks).astype(bool)
    skip_mask = analysis.water_mask.astype(bool) | snow_mask

    for _ in range(passes):
        local_mean = uniform_filter(heightmap, size=size, mode="nearest")
        excess     = heightmap - local_mean
        apply_mask = (excess >= min_shave_blocks) & ~skip_mask
        delta      = np.where(apply_mask, np.clip(-excess, -max_change_per_pass, 0.0), 0.0)
        heightmap  = heightmap + delta

    new_heights = np.round(heightmap).astype(np.int32)
    old_heights = analysis.heightmap_ground.astype(np.int32)

    _GRASS_RESKIN: frozenset[str] = frozenset({
        "minecraft:dirt", "minecraft:coarse_dirt",
        "minecraft:rooted_dirt", "minecraft:podzol",
        "minecraft:grass_block",
    })

    for i in range(w):
        for j in range(d):
            original_y = int(old_heights[i, j])
            new_y      = int(new_heights[i, j])
            if new_y >= original_y:
                continue
            x, z = area.index_to_world(i, j)

            air_positions = [(x, y, z) for y in range(new_y + 1, original_y + 1)]
            editor.placeBlock(air_positions, Block("minecraft:air"))

            surface_bid = str(surface_blocks[i, j]).lower()
            if any(sid in surface_bid for sid in _GRASS_RESKIN):
                editor.placeBlock((x, new_y, z), Block("minecraft:grass_block"))

    analysis.heightmap_ground[:, :] = new_heights
    logger.info("terraform_area (smooth): done (%d passes, radius=%d).", passes, smooth_radius)


def _terraform_platform(
    editor:              Editor,
    analysis:            WorldAnalysisResult,
    plots:               list[Plot],
    exclude_plots:       list[Plot] | None,
    allowed_mask:        np.ndarray | None,
    fill_width:          int | None,
    fill_depth:          int | None,
    fill_moat_perimeter: bool,
    moat_extra:          int,
    fill_plot_support:   bool,
    fill_area:           bool,
    use_world_scan:      bool,
    max_scan_depth:      int | None,
    connect_fill_gaps:   bool,
    outer_blend_width:   int,
    use_fill_command:    bool,
    block_type:          str,
) -> None:
    """
    Additive platform fill — raises terrain to min(plot.y), no shaving.
    """
    area = analysis.best_area
    old_heights = analysis.heightmap_ground.astype(np.int32)
    hm_rows, hm_cols = old_heights.shape

    if allowed_mask is not None and allowed_mask.shape != (hm_rows, hm_cols):
        raise ValueError(
            f"allowed_mask shape {allowed_mask.shape} != {(hm_rows, hm_cols)}"
        )

    fill_w = hm_rows if fill_width is None else max(1, min(int(fill_width), hm_rows))
    fill_d = hm_cols if fill_depth is None else max(1, min(int(fill_depth), hm_cols))

    target_y   = int(min(int(p.y) for p in plots))
    min_scan_y = int(getattr(area, "y_from", -64))
    new_heights = old_heights.copy()

    if fill_plot_support:
        can_scan = bool(use_world_scan) and hasattr(editor, "getBlock")
        for plot in plots:
            x0 = max(plot.x_from, area.x_from)
            z0 = max(plot.z_from, area.z_from)
            x1 = min(plot.x_to,   area.x_to)
            z1 = min(plot.z_to,   area.z_to)
            if x0 > x1 or z0 > z1:
                continue
            i0, j0 = area.world_to_index(x0, z0)
            i1, j1 = area.world_to_index(x1, z1)
            floor_y = int(plot.y)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    if allowed_mask is not None and not bool(allowed_mask[i, j]):
                        continue
                    x, z = area.index_to_world(i, j)
                    if can_scan:
                        bridged = bridge_void_under_floor(
                            editor, x, z, floor_y, min_scan_y, block_type,
                            use_fill_command=use_fill_command,
                        )
                        if bridged:
                            new_heights[i, j] = max(int(new_heights[i, j]), floor_y - 1)
                    else:
                        cur = int(new_heights[i, j])
                        if cur < floor_y - 1:
                            _fill_vertical_column(
                                editor, x, z, cur + 1, floor_y - 1, block_type,
                                use_fill_command=use_fill_command,
                            )
                            new_heights[i, j] = max(cur, floor_y - 1)

    if not fill_area:
        analysis.heightmap_ground[:, :] = new_heights
        return

    exclude_mask = np.zeros((hm_rows, hm_cols), dtype=bool)
    if exclude_plots:
        for plot in exclude_plots:
            x0 = max(plot.x_from, area.x_from)
            z0 = max(plot.z_from, area.z_from)
            x1 = min(plot.x_to,   area.x_to)
            z1 = min(plot.z_to,   area.z_to)
            if x0 > x1 or z0 > z1:
                continue
            i0, j0 = area.world_to_index(x0, z0)
            i1, j1 = area.world_to_index(x1, z1)
            exclude_mask[i0:i1 + 1, j0:j1 + 1] = True

    fill_mask = np.zeros((hm_rows, hm_cols), dtype=bool)
    fill_mask[:fill_w, :fill_d] = True
    if allowed_mask is not None:
        fill_mask &= allowed_mask.astype(bool)
    fill_mask &= ~exclude_mask

    if connect_fill_gaps:
        fill_mask = binary_closing(fill_mask, structure=np.ones((3, 3), dtype=bool))

    raised = 0
    for i in range(fill_w):
        for j in range(fill_d):
            if not bool(fill_mask[i, j]):
                continue
            x, z = area.index_to_world(i, j)
            current_y = int(new_heights[i, j])
            if current_y >= target_y:
                continue
            _fill_vertical_column(
                editor, x, z, current_y + 1, target_y, block_type,
                use_fill_command=use_fill_command,
            )
            new_heights[i, j] = target_y
            raised += 1

    if outer_blend_width > 0:
        max_fill_gap = outer_blend_width + 2
        for ox in range(area.x_from - outer_blend_width, area.x_to + outer_blend_width + 1):
            for oz in range(area.z_from - outer_blend_width, area.z_to + outer_blend_width + 1):
                if area.x_from <= ox <= area.x_to and area.z_from <= oz <= area.z_to:
                    continue
                cheb = max(
                    max(0, area.x_from - ox, ox - area.x_to),
                    max(0, area.z_from - oz, oz - area.z_to),
                )
                if cheb > outer_blend_width:
                    continue
                cap_y = target_y - cheb
                if cap_y <= 0:
                    continue
                li = max(0, min(hm_rows - 1, ox - area.x_from))
                lj = max(0, min(hm_cols - 1, oz - area.z_from))
                current_y = int(new_heights[li, lj])
                if current_y >= cap_y:
                    continue
                if cap_y - current_y > max_fill_gap:
                    continue
                _fill_vertical_column(
                    editor, ox, oz, current_y + 1, cap_y, block_type,
                    use_fill_command=use_fill_command,
                )

    analysis.heightmap_ground[:, :] = new_heights
    logger.info(
        "terraform_area (platform): target_y=%d, %d cells raised.", target_y, raised,
    )


# ---------------------------------------------------------------------------
# fill_depressions  (replaces fill_all_holes + seal_cave_openings)
# ---------------------------------------------------------------------------

def fill_depressions(
    editor:               Editor,
    analysis:             WorldAnalysisResult,
    config=None,
    depression_threshold: int = 3,
    border:               int = 2,
    slope_width:          int = 3,
    fill_block:           str = "minecraft:dirt",
    top_block:            str = "minecraft:grass_block",
) -> None:
    """
    Detect terrain depressions within best_area (expanded by `border` blocks
    on all sides) and fill them solid from the floor upward.

    Algorithm
    ---------
    1. Expand the search area by `border` blocks beyond best_area on all sides.
    2. Load a fresh heightmap for that expanded area.
    3. Run _fill_sinks to find which cells should be raised and to what Y.
    4. For each changed cell, fill from `base_y` upward to the target surface Y,
       where base_y = max(area_min_y - surface_scan_depth, area_min_y).
       This ensures deep holes, ravines, and cave entrances are completely solid
       rather than just surface-capped.
    5. Update analysis.heightmap_ground in-place for every filled cell.

    Parameters
    ----------
    editor               : GDPC Editor
    analysis             : WorldAnalysisResult — heightmap_ground updated in-place
    config               : TerrainConfig — provides surface_scan_depth (default 32)
    depression_threshold : min deficit below lowest neighbour to flag as pit (default 3)
    border               : blocks to expand search beyond best_area on each side (default 2)
    slope_width          : reserved for future tapering (currently unused)
    fill_block           : subsurface fill material
    top_block            : surface cap material
    """
    area = analysis.best_area

    # Expand search rect by `border` on all sides
    search_rect = Rect(
        (area.x_from - border, area.z_from - border),
        (area.x_to - area.x_from + 1 + 2 * border,
         area.z_to - area.z_from + 1 + 2 * border),
    )

    # Load heightmap for the expanded area
    world_slice = editor.loadWorldSlice(search_rect, cache=True)
    # Use MOTION_BLOCKING_NO_LEAVES — closest available worldslice type to
    # MOTION_BLOCKING_NO_PLANTS (which the HTTP API exposes but GDPC worldslice
    # does not). The -1 converts first-air Y to surface block Y.
    hm_raw      = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"]
    heightmap   = np.array(hm_raw, dtype=np.int32) - 1

    logger.info("fill_depressions: searching expanded area (border=%d)...", border)

    # Priority-flood sink fill — each cell raised only to meet its neighbours,
    # preserving slopes and hills while sealing enclosed holes.
    filled_hm = _fill_sinks(heightmap, threshold=1)
    changed   = np.argwhere(filled_hm > heightmap)

    if len(changed) == 0:
        logger.info("fill_depressions: no sinks found.")
        return

    logger.info("fill_depressions: filling %d sink cells...", len(changed))

    # Log bounding box of all changed cells in world coordinates
    wx_all = search_rect.offset.x + changed[:, 0]
    wz_all = search_rect.offset.y + changed[:, 1]
    logger.info(
        "fill_depressions: affected world bbox x=[%d, %d]  z=[%d, %d]",
        int(wx_all.min()), int(wx_all.max()),
        int(wz_all.min()), int(wz_all.max()),
    )

    # Base Y: fill from the lowest surface in the area, but never deeper than
    # surface_scan_depth blocks below that minimum (TerrainConfig default: 32).
    scan_depth = getattr(config, "surface_scan_depth", 32) if config is not None else 32
    area_min_y = int(analysis.heightmap_ground.min())
    base_y     = max(area_min_y - scan_depth, 0)
    logger.info(
        "fill_depressions: area_min_y=%d  base_y=%d (scan_depth=%d).",
        area_min_y, base_y, scan_depth,
    )

    total_filled = 0
    for li, lj in changed:
        li, lj   = int(li), int(lj)
        wx       = search_rect.offset.x + li
        wz       = search_rect.offset.y + lj
        target_y = int(filled_hm[li, lj])
        logger.debug("  fill (%d, %d)  base=%d → target=%d", wx, wz, base_y, target_y)

        # Fill from base_y to one below surface with fill_block, cap at target_y.
        for y in range(base_y, target_y):
            editor.placeBlock((wx, y, wz), Block(fill_block))
        editor.placeBlock((wx, target_y, wz), Block(top_block))

        heightmap[li, lj] = target_y
        total_filled += 1

        # Update analysis heightmap in-place
        if area.contains_xz(wx, wz):
            ix = wx - area.x_from
            iz = wz - area.z_from
            analysis.heightmap_ground[ix, iz] = target_y

    logger.info("fill_depressions: filled %d cells.", total_filled)


# ---------------------------------------------------------------------------
# terraform_perimeter
# ---------------------------------------------------------------------------

def terraform_perimeter(
    editor:     Editor,
    analysis:   WorldAnalysisResult,
    config:     SettlementConfig,
    fill_block: str = "minecraft:dirt",
    top_block:  str = "minecraft:grass_block",
) -> None:
    """
    Level the perimeter band around best_area so the fortification wall
    sits on flat ground. For each wall side, samples all heights along the
    wall line, computes the median, then fills or cuts to that level.

    Call after fill_depressions, before FortificationBuilder.build().
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground
    mid       = config.tower_width // 2

    wall_lines = {
        "north": [(x, area.z_from - mid - 1) for x in range(area.x_from, area.x_to + 1)],
        "south": [(x, area.z_to  + mid + 1) for x in range(area.x_from, area.x_to + 1)],
        "west":  [(area.x_from - mid - 1, z) for z in range(area.z_from, area.z_to + 1)],
        "east":  [(area.x_to  + mid + 1, z) for z in range(area.z_from, area.z_to + 1)],
    }

    for side, cells in wall_lines.items():
        heights = []
        for wx, wz in cells:
            li = max(0, min(heightmap.shape[0] - 1, wx - area.x_from))
            lj = max(0, min(heightmap.shape[1] - 1, wz - area.z_from))
            heights.append(int(heightmap[li, lj]))

        target_y = int(np.median(heights))
        logger.info(
            "Perimeter %s: median=%d  min=%d  max=%d",
            side, target_y, min(heights), max(heights),
        )

        for wx, wz in cells:
            li = max(0, min(heightmap.shape[0] - 1, wx - area.x_from))
            lj = max(0, min(heightmap.shape[1] - 1, wz - area.z_from))
            current_y = int(heightmap[li, lj])

            if current_y < target_y:
                for y in range(current_y + 1, target_y):
                    editor.placeBlock((wx, y, wz), Block(fill_block))
                editor.placeBlock((wx, target_y, wz), Block(top_block))
                heightmap[li, lj] = target_y
            elif current_y > target_y:
                for y in range(target_y + 1, current_y + 1):
                    editor.placeBlock((wx, y, wz), Block("minecraft:air"))
                heightmap[li, lj] = target_y


# ---------------------------------------------------------------------------
# clear_area
# ---------------------------------------------------------------------------

def clear_area(
    editor:   Editor,
    analysis: WorldAnalysisResult,
    plot:     Plot,
    config:   TerrainConfig,
    buffer:   int = 3,
) -> None:
    """
    Clear vegetation in a circular area around a plot.

    Iterates over cells within a circle of radius = max(width, depth)//2 + buffer
    and replaces any vegetation blocks with air.
    """
    center_x = int(plot.center_x)
    center_z  = int(plot.center_z)
    radius    = max(plot.width, plot.depth) // 2 + buffer
    radius_sq = radius ** 2
    h_shape   = analysis.heightmap_ground.shape
    keywords  = config.vegetation_block_keywords

    for x in range(center_x - radius, center_x + radius + 1):
        for z in range(center_z - radius, center_z + radius + 1):
            if (x - center_x) ** 2 + (z - center_z) ** 2 > radius_sq:
                continue

            gx = x - analysis.best_area.x_from
            gz = z - analysis.best_area.z_from

            if not (0 <= gx < h_shape[0] and 0 <= gz < h_shape[1]):
                continue

            ground  = int(analysis.heightmap_ground[gx, gz])
            surface = int(analysis.heightmap_surface[gx, gz])

            for y in range(ground, surface + 1):
                block    = editor.getBlock((x, y, z))
                block_id = block.id.lower()
                if any(kw in block_id for kw in keywords):
                    editor.placeBlock((x, y, z), Block("minecraft:air"))


# ---------------------------------------------------------------------------
# level_plot_area
# ---------------------------------------------------------------------------

def level_plot_area(editor: Editor, analysis: any, plot: Plot, blend_radius: int = 3):
    """
    Gentle Leveling: Instead of a flat cut, we create a soft transition
    between the house foundation and the surrounding terrain.
    """
    area = analysis.best_area
    hm = analysis.heightmap_ground.astype(np.float32)
    rows, cols = hm.shape

    clear_area(editor, analysis, plot, TerrainConfig(), buffer=blend_radius)

    # Convert plot world coords → local array indices, clamped to array bounds
    ix0 = int(np.clip(plot.x - area.x_from, 0, rows))
    ix1 = int(np.clip(plot.x - area.x_from + plot.width,  0, rows))
    iz0 = int(np.clip(plot.z - area.z_from, 0, cols))
    iz1 = int(np.clip(plot.z - area.z_from + plot.depth,  0, cols))

    if ix0 >= ix1 or iz0 >= iz1:
        # Plot footprint lies entirely outside the analysed area — skip
        return

    # 1. Define the footprint mask in local index space
    mask = np.zeros((rows, cols), dtype=bool)
    mask[ix0:ix1, iz0:iz1] = True

    # 2. Target elevation — median height inside the footprint
    footprint_heights = hm[mask]
    if footprint_heights.size == 0 or np.all(np.isnan(footprint_heights)):
        return
    target_y = int(np.nanmedian(footprint_heights))

    # Update the plot's y so callers get the correct ground level back
    plot.y = target_y

    # 3. Create a Blending Weight Map
    dist_map = distance_transform_edt(~mask)
    weights = np.clip(1.0 - (dist_map / max(blend_radius, 1)), 0, 1)
    weights = 3 * weights**2 - 2 * weights**3  # smoothstep

    # 4. Interpolate Heights
    new_hm = (target_y * weights) + (hm * (1 - weights))

    # 5. Apply to Minecraft only where the height actually changed
    affected_coords = np.argwhere(weights > 0)
    for ix, iz in affected_coords:
        old_y = int(hm[ix, iz])
        new_y = int(new_hm[ix, iz])
        if old_y != new_y:
            world_x = area.x_from + ix
            world_z = area.z_from + iz
            fill_column(editor, world_x, world_z, old_y, new_y, target_y)
            hm[ix, iz] = new_y

def fill_column(editor: Editor, x: int, z: int, y_from: int, y_to: int, target_y: int):
    """Helper to handle both filling up and shaving down."""
    if y_to > y_from: # Filling up
        for y in range(y_from, y_to + 1):
            editor.placeBlock((x, y, z), Block("minecraft:dirt"))
    else: # Shaving down
        for y in range(y_to + 1, y_from + 1):
            editor.placeBlock((x, y, z), Block("minecraft:air"))


# ---------------------------------------------------------------------------
# remove_sparse_top
# ---------------------------------------------------------------------------

def remove_sparse_top(
    editor:                    Editor,
    analysis:                  WorldAnalysisResult,
    districts:                 Districts | None = None,
    settlement_config:         SettlementConfig | None = None,
    sparse_threshold:          float = 0.08,
    min_height_above_dominant: int   = 5,
    max_height_above_dominant: int   = 12,
    max_terrain_std:           float = 12.0,
    building_buffer:           int   = 2,
    edge_buffer:               int   = 1,
    slope_width:               int   = 2,
    max_aspect_ratio:          float = 3.0,
    gap_block_samples:         int   = 10,
) -> None:
    """
    Remove sparse terrain clusters above the dominant flat level naturally,
    preserving player-built structures and tapering edges to avoid sharp drops.

    Algorithm
    ---------
    1. Find the dominant height level (largest contiguous flat patch).
    2. For each height level above dominant, find contiguous clusters.
    3. Skip a cluster if ANY of these hold:
       a) area >= sparse_threshold × dominant_area  (not sparse enough)
       b) height above dominant < min_height_above_dominant  (too shallow)
       c) height above dominant > max_height_above_dominant  (mountainous)
       d) terrain std > max_terrain_std  (mountainous area — skip entirely)
       e) bounding box fits the district-specific plot + buffer  (buildable)
       f) any non-natural block found in the cluster  (player structure)
    4. For each candidate cluster:
       - Cells within edge_buffer: untouched.
       - Cells within edge_buffer + slope_width: tapered to intermediate height.
       - Interior cells: removed to dominant_y.
    5. Shave narrow stripes and fill enclosed gaps.
    """
    from scipy.ndimage import distance_transform_edt

    area   = analysis.best_area
    submap = analysis.heightmap_ground.copy()
    w, d   = submap.shape

    terrain_std = float(np.std(submap))
    if terrain_std > max_terrain_std:
        logger.info(
            "remove_sparse_top: terrain std=%.1f > %.1f — skipping (mountainous area).",
            terrain_std, max_terrain_std,
        )
        return

    unique_heights = np.unique(submap)
    dominant_y     = int(unique_heights[0])
    dominant_area  = 0
    height_clusters: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for y in unique_heights:
        flat_mask    = (submap == y)
        labeled, num = ndimage_label(flat_mask)
        if num == 0:
            continue
        sizes = np.bincount(labeled.ravel())[1:]
        height_clusters[int(y)] = (labeled, sizes)
        largest = int(sizes.max())
        if largest > dominant_area:
            dominant_area = largest
            dominant_y    = int(y)

    if dominant_area == 0:
        return

    sparse_limit = sparse_threshold * dominant_area

    _fallback_w = _fallback_d = 8
    if settlement_config is not None:
        _fallback_w = max(settlement_config.plot_width.values(),  default=8)
        _fallback_d = max(settlement_config.plot_depth.values(),  default=8)

    def _min_buildable(cx: int, cz: int) -> tuple[int, int]:
        if districts is None or settlement_config is None:
            return _fallback_w + 2 * building_buffer, _fallback_d + 2 * building_buffer
        dm_x, dm_z = cx, cz
        if not (0 <= dm_x < districts.map.shape[0] and
                0 <= dm_z < districts.map.shape[1]):
            return _fallback_w + 2 * building_buffer, _fallback_d + 2 * building_buffer
        district_idx = int(districts.map[dm_x, dm_z])
        dtype        = districts.types.get(district_idx, "residential")
        plot_w       = settlement_config.plot_width.get(dtype, _fallback_w)
        plot_d       = settlement_config.plot_depth.get(dtype, _fallback_d)
        return plot_w + 2 * building_buffer, plot_d + 2 * building_buffer

    # Step 2 & 3: remove sparse clusters above dominant
    for y in unique_heights:
        y = int(y)
        if y <= dominant_y:
            continue
        if y - dominant_y > max_height_above_dominant:
            continue

        labeled, sizes = height_clusters.get(y, (None, None))
        if labeled is None:
            continue

        label_ids  = np.arange(1, len(sizes) + 1)
        sparse_ids = label_ids[sizes < sparse_limit]

        for lid in sparse_ids:
            cells = np.argwhere(labeled == lid)

            bb_w       = int(cells[:, 0].max() - cells[:, 0].min() + 1)
            bb_d       = int(cells[:, 1].max() - cells[:, 1].min() + 1)
            centroid_x = int(cells[:, 0].mean())
            centroid_z = int(cells[:, 1].mean())
            min_w, min_d = _min_buildable(centroid_x, centroid_z)
            if bb_w >= min_w and bb_d >= min_d:
                continue

            cluster_has_structure = False
            for cx, cz in cells:
                cx, cz    = int(cx), int(cz)
                current_y = int(submap[cx, cz])
                wx, wz    = area.index_to_world(cx, cz)
                block     = editor.getBlock((wx, current_y, wz))
                if not _is_natural(block.id):
                    cluster_has_structure = True
                    break
            if cluster_has_structure:
                continue

            cluster_heights = np.array([int(submap[int(cx), int(cz)]) for cx, cz in cells])
            if int(cluster_heights.max()) - dominant_y < min_height_above_dominant:
                continue

            cluster_mask_local = np.zeros((w, d), dtype=bool)
            for cx, cz in cells:
                cluster_mask_local[int(cx), int(cz)] = True
            dist_map = distance_transform_edt(cluster_mask_local)

            for cx, cz in cells:
                cx, cz    = int(cx), int(cz)
                cell_dist = float(dist_map[cx, cz])
                current_y = int(submap[cx, cz])
                wx, wz    = area.index_to_world(cx, cz)

                if cell_dist <= edge_buffer:
                    continue
                elif cell_dist <= edge_buffer + slope_width:
                    slope_t  = (cell_dist - edge_buffer) / slope_width
                    target_y = int(current_y - slope_t * (current_y - dominant_y))
                    target_y = max(target_y, dominant_y)
                    positions = [(wx, wy, wz) for wy in range(target_y + 1, current_y + 1)]
                    if positions:
                        editor.placeBlock(positions, Block("minecraft:air"))
                    editor.placeBlock((wx, target_y, wz), Block("minecraft:grass_block"))
                    submap[cx, cz] = target_y
                else:
                    positions = [(wx, wy, wz) for wy in range(dominant_y + 1, current_y + 1)]
                    if positions:
                        editor.placeBlock(positions, Block("minecraft:air"))
                    editor.placeBlock((wx, dominant_y, wz), Block("minecraft:grass_block"))
                    submap[cx, cz] = dominant_y

    # Step 4: shave narrow stripes
    current_submap = submap.copy()
    any_changed = True
    while any_changed:
        any_changed = False
        for y in np.unique(current_submap):
            y = int(y)
            if y <= dominant_y:
                continue
            if y - dominant_y > max_height_above_dominant:
                continue
            flat_mask      = (current_submap == y)
            labeled, num   = ndimage_label(flat_mask)
            if num == 0:
                continue
            sizes     = np.bincount(labeled.ravel())[1:]
            label_ids = np.arange(1, len(sizes) + 1)
            for lid in label_ids:
                cells = np.argwhere(labeled == lid)
                bb_w  = int(cells[:, 0].max() - cells[:, 0].min() + 1)
                bb_d  = int(cells[:, 1].max() - cells[:, 1].min() + 1)
                short = min(bb_w, bb_d)
                long_ = max(bb_w, bb_d)
                if short == 0 or long_ / short <= max_aspect_ratio:
                    continue
                for cx, cz in cells:
                    cx, cz = int(cx), int(cz)
                    wx, wz = area.index_to_world(cx, cz)
                    editor.placeBlock((wx, y, wz), Block("minecraft:air"))
                    editor.placeBlock((wx, y - 1, wz), Block("minecraft:grass_block"))
                    current_submap[cx, cz] = y - 1
                    submap[cx, cz]         = y - 1
                any_changed = True

    # Step 5: fill enclosed gaps
    dominant_cells = np.argwhere(submap == dominant_y)
    fill_block_id  = "minecraft:dirt"
    if len(dominant_cells) > 0:
        sample_count = min(gap_block_samples, len(dominant_cells))
        indices      = np.random.choice(len(dominant_cells), size=sample_count, replace=False)
        block_counts: dict[str, int] = {}
        for idx in indices:
            cx, cz  = int(dominant_cells[idx, 0]), int(dominant_cells[idx, 1])
            wx, wz  = area.index_to_world(cx, cz)
            block   = editor.getBlock((wx, dominant_y, wz))
            bid     = block.id.lower()
            if bid and bid != "minecraft:air":
                block_counts[bid] = block_counts.get(bid, 0) + 1
        if block_counts:
            fill_block_id = max(block_counts, key=block_counts.get)

    fill_blk       = Block(fill_block_id)
    below_dominant = (submap < dominant_y)
    at_dominant    = (submap == dominant_y)
    neighbour_count = (
        at_dominant[2:,   1:-1].astype(np.int8) +
        at_dominant[:-2,  1:-1].astype(np.int8) +
        at_dominant[1:-1, 2:  ].astype(np.int8) +
        at_dominant[1:-1, :-2 ].astype(np.int8)
    )
    gap_mask = np.zeros((w, d), dtype=bool)
    gap_mask[1:-1, 1:-1] = below_dominant[1:-1, 1:-1] & (neighbour_count >= 3)

    for cx, cz in np.argwhere(gap_mask):
        cx, cz = int(cx), int(cz)
        wx, wz = area.index_to_world(cx, cz)
        gap_y  = int(submap[cx, cz])
        positions = [(wx, wy, wz) for wy in range(gap_y + 1, dominant_y + 1)]
        if positions:
            editor.placeBlock(positions, fill_blk)
        submap[cx, cz] = dominant_y

    analysis.heightmap_ground[:, :] = submap


# ---------------------------------------------------------------------------
# clear_lava_pools
# ---------------------------------------------------------------------------

def clear_lava_pools(
    editor: Editor,
    analysis: WorldAnalysisResult,
) -> None:
    """
    Clear surface lava pools and fill them flush with the surrounding terrain.

    Two-pass detection ensures lava is found regardless of how the heightmaps
    report it:

    Pass A — ``surface_blocks`` already contains ``"lava"`` for cells where
             the fetcher's downward scan hit a lava block.
    Pass B — any cell where ``water_mask`` is True (fluid detected) but
             ``surface_blocks`` is NOT water is probed with ``getBlock()``
             at ``heightmap_surface - 1`` to catch lava that the surface
             scanner missed.

    For each lava cell the column is filled with stone from 6 blocks below
    the lava up to the surrounding terrain level, then capped with grass.
    """
    area       = analysis.best_area
    heightmap  = analysis.heightmap_ground
    h_surface  = analysis.heightmap_surface
    water_mask = analysis.water_mask.astype(bool)
    h, w       = heightmap.shape

    lava_mask = np.vectorize(
        lambda b: "lava" in str(b).lower()
    )(analysis.surface_blocks).astype(bool)

    fluid_but_unknown = water_mask & ~lava_mask
    probe_cells = np.argwhere(fluid_but_unknown)
    probed = 0
    for ix, iz in probe_cells:
        ix, iz = int(ix), int(iz)
        wx, wz = area.index_to_world(ix, iz)
        probe_y = int(h_surface[ix, iz]) - 1
        try:
            block = editor.getBlock((wx, probe_y, wz))
            if "lava" in block.id.lower():
                lava_mask[ix, iz] = True
                probed += 1
        except Exception:
            pass

    lava_cells = np.argwhere(lava_mask)
    if len(lava_cells) == 0:
        logger.info("clear_lava_pools: no surface lava found.")
        return

    logger.info(
        "clear_lava_pools: clearing %d lava cell(s) (%d from probe).",
        len(lava_cells), probed,
    )

    fill_heights = np.empty(len(lava_cells), dtype=np.int32)
    for k, (ix, iz) in enumerate(lava_cells):
        neighbour_ys: list[int] = []
        for di in (-2, -1, 0, 1, 2):
            for dj in (-2, -1, 0, 1, 2):
                ni = int(np.clip(ix + di, 0, h - 1))
                nj = int(np.clip(iz + dj, 0, w - 1))
                if not lava_mask[ni, nj]:
                    neighbour_ys.append(int(heightmap[ni, nj]))
        if neighbour_ys:
            fill_top = int(np.median(neighbour_ys))
        else:
            fill_top = int(heightmap[ix, iz])
        fill_top = max(fill_top, int(heightmap[ix, iz]))
        fill_heights[k] = fill_top

    for k, (ix, iz) in enumerate(lava_cells):
        ix, iz   = int(ix), int(iz)
        wx, wz   = area.index_to_world(ix, iz)
        cell_y   = int(heightmap[ix, iz])
        fill_top = int(fill_heights[k])

        fill_range = range(cell_y - 6, fill_top)
        if fill_range:
            editor.placeBlock(
                [(wx, wy, wz) for wy in fill_range],
                Block("minecraft:stone"),
            )
        editor.placeBlock((wx, fill_top, wz), Block("minecraft:grass_block"))

        heightmap[ix, iz] = fill_top


# ---------------------------------------------------------------------------
# fill_below_surface
# ---------------------------------------------------------------------------

def fill_below_surface(
    editor:        Editor,
    analysis:      WorldAnalysisResult,
    target_height: int,
    sample_radius: int = 3,
) -> None:
    """
    Fill all cells below target_height using blocks sampled from neighbouring
    surface cells, weighted by inverse distance.
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground
    w, d      = heightmap.shape

    offsets: list[tuple[int, int, float]] = []
    for dx in range(-sample_radius, sample_radius + 1):
        for dz in range(-sample_radius, sample_radius + 1):
            if dx == 0 and dz == 0:
                continue
            dist = (dx * dx + dz * dz) ** 0.5
            offsets.append((dx, dz, 1.0 / dist))

    below_mask = heightmap < target_height
    cells      = np.argwhere(below_mask)
    if len(cells) == 0:
        return

    for cx, cz in cells:
        cx, cz = int(cx), int(cz)
        cell_y = int(heightmap[cx, cz])
        if cell_y >= target_height:
            continue

        block_weights: dict[str, float] = {}
        for dx, dz, weight in offsets:
            nx, nz = cx + dx, cz + dz
            if not (0 <= nx < w and 0 <= nz < d):
                continue
            neighbour_y = int(heightmap[nx, nz])
            if neighbour_y < target_height:
                continue
            wx, wz  = area.index_to_world(nx, nz)
            block   = editor.getBlock((wx, neighbour_y, wz))
            bid     = block.id.lower()
            if not bid or bid == "minecraft:air":
                continue
            block_weights[bid] = block_weights.get(bid, 0.0) + weight

        if not block_weights:
            continue

        fill_blk  = Block(max(block_weights, key=block_weights.get))
        wx, wz    = area.index_to_world(cx, cz)
        positions = [(wx, wy, wz) for wy in range(cell_y + 1, target_height + 1)]
        if positions:
            editor.placeBlock(positions, fill_blk)
        heightmap[cx, cz] = target_height


# ---------------------------------------------------------------------------
# recompute_all_maps
# ---------------------------------------------------------------------------

def recompute_all_maps(
    editor:   Editor,
    analysis: WorldAnalysisResult,
    config,
    *,
    terrain_loader=None,
) -> None:
    """
    Recompute all derived terrain maps from the current world state after
    any terraforming operations.

    Updated maps
    ------------
    heightmap_ground      : re-sampled via terrain_loader (MOTION_BLOCKING_NO_PLANTS)
                            if provided, otherwise via MOTION_BLOCKING_NO_LEAVES
    heightmap_surface     : re-sampled from world via MOTION_BLOCKING
    water_mask            : sampled block-by-block at ground level
    water_distances       : distance transform from updated water_mask
    slope_map             : recomputed from updated heightmap_ground
    roughness_map         : recomputed from updated heightmap_ground
    plant_thickness       : recomputed from updated surface - ground heightmaps

    heightmap_ocean_floor and biomes are not modified by terraforming so are
    left unchanged.

    Parameters
    ----------
    editor         : GDPC Editor
    analysis       : WorldAnalysisResult — all maps updated in-place
    config         : TerrainConfig — provides radius for roughness window
    terrain_loader : optional TerrainLoader — if provided, uses the HTTP API
                     for an exact MOTION_BLOCKING_NO_PLANTS ground heightmap
                     (same source used during initial world analysis)
    """
    from scipy.ndimage import (
        distance_transform_edt,
        maximum_filter,
        minimum_filter,
    )

    area = analysis.best_area

    # --- re-sample heightmaps from the world ---
    rect        = Rect((area.x_from, area.z_from), (area.width, area.depth))
    world_slice = editor.loadWorldSlice(rect, cache=False)  # cache=False forces fresh data

    # Ground heightmap: use terrain_loader (MOTION_BLOCKING_NO_PLANTS) when
    # available — same source as initial world analysis, so results are consistent.
    # Fall back to MOTION_BLOCKING_NO_LEAVES from the world slice otherwise.
    if terrain_loader is not None:
        hm_ground = np.asarray(
            terrain_loader.get_heightmap(
                area.x_from, area.z_from,
                area.width,  area.depth,
                "MOTION_BLOCKING_NO_PLANTS",
            ),
            dtype=np.int32,
        )
    else:
        hm_ground = np.array(
            world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"], dtype=np.int32
        ) - 1

    hm_surface = np.array(
        world_slice.heightmaps["MOTION_BLOCKING"], dtype=np.int32
    ) - 1

    analysis.heightmap_ground[:]  = hm_ground
    analysis.heightmap_surface[:] = hm_surface

    # --- water mask: check actual surface blocks for water ---
    # Comparing heightmaps is unreliable after fill operations shift ground
    # levels — instead sample the actual block at the ground heightmap level.
    w, d = hm_ground.shape
    new_water_mask = np.zeros((w, d), dtype=bool)
    for ix in range(w):
        for iz in range(d):
            wx, wz   = area.x_from + ix, area.z_from + iz
            surf_y   = int(hm_ground[ix, iz])
            block_id = editor.getBlock((wx, surf_y, wz)).id
            new_water_mask[ix, iz] = block_id in (
                "minecraft:water", "minecraft:flowing_water"
            )
    analysis.water_mask[:] = new_water_mask

    # --- water distances ---
    analysis.water_distances = distance_transform_edt(
        ~analysis.water_mask.astype(bool)
    ).astype(np.float32)

    # --- slope ---
    h        = hm_ground.astype(np.float32)
    gx, gz   = np.gradient(h)
    analysis.slope_map[:] = np.sqrt(gx ** 2 + gz ** 2)

    # --- roughness ---
    size = 2 * config.radius + 1
    analysis.roughness_map[:] = (
        maximum_filter(h, size=size) - minimum_filter(h, size=size)
    ).astype(np.float32)

    # --- plant thickness ---
    if analysis.plant_thickness is not None:
        analysis.plant_thickness[:] = (hm_surface - hm_ground).astype(np.float32)

    logger.info(
        "recompute_all_maps: done — ground Y range [%d, %d], water=%.1f%%.",
        int(hm_ground.min()), int(hm_ground.max()),
        float(analysis.water_mask.sum()) / analysis.water_mask.size * 100,
    )