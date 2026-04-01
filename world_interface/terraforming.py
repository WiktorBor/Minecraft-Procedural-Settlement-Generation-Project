"""Terrain modification operations for settlement generation."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np
from gdpc import Block
from gdpc.editor import Editor
from scipy.ndimage import uniform_filter

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig

logger = logging.getLogger(__name__)

_AIR_IDS: frozenset[str] = frozenset({
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
})


# ---------------------------------------------------------------------------
# terraform_area
# ---------------------------------------------------------------------------

def terraform_area(
    editor:              Editor,
    analysis:            WorldAnalysisResult,
    passes:              int   = 3,
    smooth_radius:       int   = 3,
    max_change_per_pass: float = 1.0,
) -> None:
    """
    Smooth terrain bumps within best_area using iterative neighbourhood
    averaging, producing natural slopes rather than hard flat cuts.

    Only downward smoothing is applied — cells below the local mean are
    never raised here. Hole-filling is handled by fill_all_holes().

    Algorithm
    ---------
    Each pass:
      1. Compute the neighbourhood mean via uniform filter.
      2. For cells ABOVE the mean: move down by up to max_change_per_pass.
      3. For cells BELOW the mean: leave untouched.
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground.astype(np.float32)
    w, d      = heightmap.shape
    size      = 2 * smooth_radius + 1

    for _ in range(passes):
        local_mean = uniform_filter(heightmap, size=size, mode="nearest")
        delta      = np.clip(local_mean - heightmap, -max_change_per_pass, 0.0)
        heightmap  = heightmap + delta

    new_heights = np.round(heightmap).astype(np.int32)
    old_heights = analysis.heightmap_ground.astype(np.int32)

    for i in range(w):
        for j in range(d):
            original_y = int(old_heights[i, j])
            new_y      = int(new_heights[i, j])
            if new_y >= original_y:
                continue
            x, z = area.index_to_world(i, j)
            for y in range(new_y + 1, original_y + 1):
                editor.placeBlock((x, y, z), Block("minecraft:air"))

    analysis.heightmap_ground[:, :] = new_heights
    logger.info("terraform_area: done (%d passes, radius=%d).", passes, smooth_radius)


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
    sits on flat ground rather than following terrain drops.

    For each wall side:
      1. Sample all heights along the wall line.
      2. Compute the median.
      3. Fill upward or cut downward to that median height.

    Call this AFTER terraform_area and fill_all_holes, just before
    FortificationBuilder.build().
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
# Hole data container
# ---------------------------------------------------------------------------

@dataclass
class HoleRegion:
    """
    A detected hole region with geometry and fill target pre-computed.

    Attributes
    ----------
    cells         : (local_x, local_z) index pairs in this hole.
    hole_radius   : max distance from centroid to any hole cell.
    sample_radius : hole_radius + 3 (informational).
    target_y      : Y level where the flat cap is placed (calculated from geometry).
    min_hole_y    : deepest Y in the hole (for cap depth calculation).
    size          : number of cells in the hole.
    strategy      : always "flat cap at rim" for this implementation.
    wx_centre     : world X of the hole centroid (for /tp logging).
    wz_centre     : world Z of the hole centroid.
    """
    cells:         list[tuple[int, int]]
    hole_radius:   float
    sample_radius: float
    target_y:      int
    min_hole_y:    int
    size:          int
    strategy:      str
    wx_centre:     int = 0
    wz_centre:     int = 0


# ---------------------------------------------------------------------------
# detect_hole_entries
# ---------------------------------------------------------------------------

def detect_hole_entries(
    analysis:       WorldAnalysisResult,
    hole_threshold: int = 2,
) -> list[tuple[int, int]]:
    """
    Find seed world (x, z) coordinates for holes using the heightmap.

    Three strategies combined:
      1. Sharp pits    — cell strictly below min of all 8 neighbours.
      2. Gradual bowls — cell significantly below 15x15 neighbourhood mean.
      3. Water bowls   — water cell below 9x9 neighbourhood mean.

    Ravines excluded: cells where heightmap_ground - heightmap_ocean_floor
    exceeds 8 are deep chasms left for seal_cave_openings.

    Returns one seed (world x, z) per connected hole region — the deepest
    cell in each region is chosen as the BFS entry point.

    Parameters
    ----------
    analysis        : WorldAnalysisResult
    hole_threshold  : minimum deficit to flag as a hole (default 2)

    Returns
    -------
    list of (wx, wz) world coordinate tuples
    """
    from scipy.ndimage import grey_erosion, binary_dilation, label as ndimage_label

    heightmap  = analysis.heightmap_ground.astype(np.float32)
    water_mask = analysis.water_mask.astype(bool)
    area       = analysis.best_area
    w, d       = heightmap.shape

    # Ravine exclusion — deep chasms left for seal_cave_openings
    depth_skip = 8
    if analysis.heightmap_ocean_floor is not None:
        chasm_mask = (
            heightmap - analysis.heightmap_ocean_floor.astype(np.float32)
        ) > depth_skip
    else:
        chasm_mask = np.zeros((w, d), dtype=bool)

    # Strategy 1: sharp pits
    footprint       = np.ones((3, 3), dtype=bool)
    footprint[1, 1] = False
    neighbour_min   = grey_erosion(heightmap, footprint=footprint, mode="nearest")
    sharp_holes     = (neighbour_min - heightmap >= hole_threshold) & ~chasm_mask

    # Strategy 2: gradual dry bowls
    mean_wide     = uniform_filter(heightmap, size=15, mode="nearest")
    gradual_bowls = (
        (mean_wide - heightmap >= hole_threshold + 1)
        & ~water_mask
        & ~chasm_mask
    )

    # Strategy 3: water-filled bowls
    mean_terrain = uniform_filter(heightmap, size=9, mode="nearest")
    water_bowls  = (
        water_mask
        & (mean_terrain - heightmap >= hole_threshold)
        & ~chasm_mask
    )

    water_buffer = binary_dilation(water_mask, iterations=1)
    hole_mask    = (
        ((sharp_holes | gradual_bowls) & ~water_buffer)
        | water_bowls
    )

    n_sharp   = int(np.sum(sharp_holes & ~water_buffer))
    n_gradual = int(np.sum(gradual_bowls & ~water_buffer))
    n_water   = int(np.sum(water_bowls))
    logger.info(
        "detect_hole_entries: %d cells (%d sharp + %d gradual + %d water) threshold=%d.",
        int(np.sum(hole_mask)), n_sharp, n_gradual, n_water, hole_threshold,
    )

    if not np.any(hole_mask):
        return []

    # One entry per connected region — deepest cell in each
    labeled, num = ndimage_label(hole_mask)
    entries: list[tuple[int, int]] = []

    for hole_id in range(1, num + 1):
        cells   = np.argwhere(labeled == hole_id)
        depths  = [float(heightmap[int(c[0]), int(c[1])]) for c in cells]
        deepest = cells[int(np.argmin(depths))]
        wx, wz  = area.index_to_world(int(deepest[0]), int(deepest[1]))
        entries.append((wx, wz))

    logger.info("detect_hole_entries: %d entry points.", len(entries))
    return entries


# ---------------------------------------------------------------------------
# flood_fill_hole
# ---------------------------------------------------------------------------

def flood_fill_hole(
    editor:     Editor,
    analysis:   WorldAnalysisResult,
    entry_wx:   int,
    entry_wz:   int,
    max_radius: int = 30,
) -> HoleRegion | None:
    """
    From a seed point, BFS outward on the heightmap surface to find
    all cells that are part of the same depression.

    Expansion logic:
      - Neighbour at or below entry_y → part of the hole, expand.
      - Neighbour above entry_y       → rim cell, record height, stop.
      - Manhattan distance >= max_radius → stop expanding.

    target_y = min(rim_y) — the Y where the ground starts dropping,
    which is where the flat cap will be placed.

    Parameters
    ----------
    editor      : GDPC Editor (not queried here — heightmap only)
    analysis    : WorldAnalysisResult
    entry_wx    : world X of the seed point
    entry_wz    : world Z of the seed point
    max_radius  : Manhattan distance limit for BFS (default 30)

    Returns
    -------
    HoleRegion or None if entry is not a valid hole.
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground
    w, d      = heightmap.shape

    try:
        ix0, iz0 = area.world_to_index(entry_wx, entry_wz)
    except ValueError:
        return None

    entry_y = int(heightmap[ix0, iz0])

    visited:  set[tuple[int, int]] = {(ix0, iz0)}
    hole_xz:  list[tuple[int, int]] = [(ix0, iz0)]
    rim_y:    list[int] = []
    hole_y:   list[int] = [entry_y]  # Track all Y values in the hole
    queue:    deque[tuple[int, int]] = deque([(ix0, iz0)])
    cx_sum    = ix0
    cz_sum    = iz0

    while queue:
        ix, iz = queue.popleft()

        for dix, diz in ((1,0),(-1,0),(0,1),(0,-1)):
            nix, niz = ix + dix, iz + diz
            if not (0 <= nix < w and 0 <= niz < d):
                continue
            if (nix, niz) in visited:
                continue
            visited.add((nix, niz))

            ny = int(heightmap[nix, niz])

            if abs(nix - ix0) + abs(niz - iz0) >= max_radius:
                rim_y.append(ny)
                continue

            if ny <= entry_y:
                # Still inside the depression — expand
                hole_xz.append((nix, niz))
                hole_y.append(ny)  # Track this hole cell's height
                cx_sum += nix
                cz_sum += niz
                queue.append((nix, niz))
            else:
                # Higher than entry — this is the rim
                rim_y.append(ny)

    if not rim_y:
        return None

    hole_size   = len(hole_xz)
    cx_mean     = cx_sum / hole_size
    cz_mean     = cz_sum / hole_size
    hole_radius = float(max(
        np.sqrt((ix - cx_mean) ** 2 + (iz - cz_mean) ** 2)
        for ix, iz in hole_xz
    )) if hole_size > 1 else 1.0

    # Calculate cap position based on hole geometry
    rim_arr  = np.array(rim_y, dtype=np.float32)
    min_rim_y = int(np.min(rim_arr))
    hole_arr = np.array(hole_y, dtype=np.float32)
    min_hole_y = int(np.min(hole_arr))
    hole_depth = min_rim_y - min_hole_y
    
    # Place cap 40% down into the hole (from rim toward floor)
    # This provides a natural-looking intermediate level
    cap_offset = int(hole_depth * 0.4)
    target_y = min_rim_y - cap_offset

    cx_local   = max(0, min(int(round(cx_mean)), w - 1))
    cz_local   = max(0, min(int(round(cz_mean)), d - 1))
    wx_c, wz_c = area.index_to_world(cx_local, cz_local)

    logger.info(
        "  Hole: size=%d  radius=%.1f  rim_n=%d  depth=%d  "
        "target_y=%d (%.0f%% down)  centre=(%d,%d,%d)  /tp %d %d %d",
        hole_size, hole_radius, len(rim_y), hole_depth,
        target_y, (cap_offset / hole_depth * 100) if hole_depth > 0 else 0,
        wx_c, target_y, wz_c,
        wx_c, target_y + 5, wz_c,
    )

    return HoleRegion(
        cells         = hole_xz,
        hole_radius   = hole_radius,
        sample_radius = hole_radius + 3,
        target_y      = target_y,
        min_hole_y    = min_hole_y,
        size          = hole_size,
        strategy      = "flat cap at rim",
        wx_centre     = wx_c,
        wz_centre     = wz_c,
    )


# ---------------------------------------------------------------------------
# fill_holes
# ---------------------------------------------------------------------------

def fill_holes(
    editor:     Editor,
    analysis:   WorldAnalysisResult,
    regions:    list[HoleRegion],
    fill_block: str = "minecraft:dirt",
    top_block:  str = "minecraft:grass_block",
    cap_depth:  int = 3,
) -> None:
    """
    Place a flat cap of cap_depth layers over each hole region.

    For each cell in the region that is below target_y:
      - Places top_block at target_y (visible surface).
      - Places fill_block at target_y-1 down to target_y-(cap_depth-1).
      - Updates analysis.heightmap_ground in-place.

    Logs Y range, block count, and /tp command for each region.

    Parameters
    ----------
    editor      : GDPC Editor
    analysis    : WorldAnalysisResult — heightmap_ground updated in-place
    regions     : list from flood_fill_hole()
    fill_block  : subsurface cap material (default: dirt)
    top_block   : surface cap material (default: grass_block)
    cap_depth   : layers to place downward from target_y (default 3)
    """
    area = analysis.best_area

    for region in regions:
        target_y = region.target_y
        y_bottom = target_y - (cap_depth - 1)
        placed   = 0

        for cx, cz in region.cells:
            current_y = int(analysis.heightmap_ground[cx, cz])
            if current_y >= target_y:
                continue

            wx, wz = area.index_to_world(cx, cz)

            # Top surface cap
            editor.placeBlock((wx, target_y, wz), Block(top_block))

            # Fill layers below the cap
            for dy in range(1, cap_depth):
                editor.placeBlock((wx, target_y - dy, wz), Block(fill_block))

            analysis.heightmap_ground[cx, cz] = target_y
            placed += 1

        logger.info(
            "  Cap placed (size=%d  depth=%d): %d blocks  "
            "Y top=%d  Y bottom=%d  "
            "centre=(%d,%d,%d)  /tp %d %d %d",
            region.size, cap_depth, placed,
            target_y, y_bottom,
            region.wx_centre, target_y, region.wz_centre,
            region.wx_centre, target_y + 5, region.wz_centre,
        )


# ---------------------------------------------------------------------------
# fill_all_holes
# ---------------------------------------------------------------------------

def fill_all_holes(
    editor:         Editor,
    analysis:       WorldAnalysisResult,
    fill_block:     str = "minecraft:dirt",
    top_block:      str = "minecraft:grass_block",
    hole_threshold: int = 2,
    max_radius:     int = 30,
    cap_depth:      int = 3,
) -> None:
    """
    Detect entry points, BFS-expand each into a HoleRegion, then place caps.

    Catches sharp pits, gradual dry bowls, and water-filled depressions.
    Ravines and open caves are left for seal_cave_openings (terrain_clearer).

    Parameters
    ----------
    editor          : GDPC Editor
    analysis        : WorldAnalysisResult — heightmap_ground updated in-place
    fill_block      : subsurface cap material (default: dirt)
    top_block       : surface cap material (default: grass_block)
    hole_threshold  : minimum deficit to flag as hole entry (default 2)
    max_radius      : BFS Manhattan radius limit per hole (default 30)
    cap_depth       : layers to place downward from cap surface (default 3)
    """
    entries = detect_hole_entries(analysis, hole_threshold=hole_threshold)
    if not entries:
        logger.info("fill_all_holes: no hole entries detected.")
        return

    logger.info("fill_all_holes: %d entry points to process.", len(entries))

    regions:      list[HoleRegion]    = []
    filled_cells: set[tuple[int,int]] = set()

    for wx, wz in entries:
        try:
            ix, iz = analysis.best_area.world_to_index(wx, wz)
        except ValueError:
            continue

        if (ix, iz) in filled_cells:
            continue  # already covered by a previous region

        region = flood_fill_hole(editor, analysis, wx, wz, max_radius=max_radius)
        if region is None:
            continue

        regions.append(region)
        for cx, cz in region.cells:
            filled_cells.add((cx, cz))

    if not regions:
        logger.info("fill_all_holes: no valid hole regions found.")
        return

    fill_holes(
        editor, analysis, regions,
        fill_block=fill_block,
        top_block=top_block,
        cap_depth=cap_depth,
    )
    logger.info("fill_all_holes: done — %d region(s) capped.", len(regions))