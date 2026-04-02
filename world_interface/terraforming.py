"""Terrain modification operations for settlement generation."""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from gdpc import Block
from gdpc.editor import Editor
from gdpc.vector_tools import Rect
from scipy.ndimage import label as ndimage_label

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig, TerrainConfig
from data.settlement_entities import Districts, Plot

logger = logging.getLogger(__name__)

_FILL_OVER: frozenset[str] = frozenset({
    "minecraft:water",
    "minecraft:flowing_water",
    "minecraft:lily_pad",
})

# Block IDs that confirm a column is genuine solid surface ground.
# Used to verify BFS seeds are real terrain, not air or structure tops.
_SOLID_SURFACE: frozenset[str] = frozenset({
    "minecraft:grass_block",
    "minecraft:dirt",
    "minecraft:coarse_dirt",
    "minecraft:podzol",
    "minecraft:rooted_dirt",
    "minecraft:mud",
    "minecraft:stone",
    "minecraft:deepslate",
    "minecraft:cobblestone",
    "minecraft:mossy_cobblestone",
    "minecraft:gravel",
    "minecraft:sand",
    "minecraft:red_sand",
    "minecraft:sandstone",
    "minecraft:red_sandstone",
    "minecraft:clay",
    "minecraft:snow_block",
    "minecraft:ice",
    "minecraft:packed_ice",
    "minecraft:mycelium",
    "minecraft:dirt_path",
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


def _is_natural(block_id: str) -> bool:
    bid = block_id.lower()
    return bid in _NATURAL_BLOCKS or any(
        bid.endswith(suffix) for suffix in (
            "_ore", "_stone", "_dirt", "_sand", "_gravel",
            "_leaves", "_log", "_wood", "_sapling",
        )
    )


# ---------------------------------------------------------------------------
# Internal helpers (depression detection + fill)
# ---------------------------------------------------------------------------

def _modal_y(heightmap: np.ndarray) -> int:
    """Most common Y value across a heightmap array."""
    values, counts = np.unique(heightmap, return_counts=True)
    return int(values[np.argmax(counts)])


def _detect_depression_rect(
    heightmap: np.ndarray,
    mode_y:    int,
    threshold: int = 3,
) -> Optional[Rect]:
    """
    Find the bounding rectangle of the most significant terrain depression —
    a tight connected cluster of abnormally deep cells, not gradual slopes.

    Algorithm
    ---------
    1. Flag cells >= threshold below mode_y as candidate depression cells.
    2. Label connected components of those cells.
    3. Score each component by: size × mean_depth (deepest, most connected
       clusters win over scattered shallow dips).
    4. Return the bounding rect of the highest-scoring component only.

    This avoids capturing natural hillside slopes that are simply lower than
    the modal level — only genuine pits and cave openings are returned.
    """
    from scipy.ndimage import label as ndimage_label

    depression_mask = heightmap <= (mode_y - threshold)
    if not depression_mask.any():
        return None

    labeled, num = ndimage_label(depression_mask)
    if num == 0:
        return None

    best_label = 1
    best_score = -1.0

    for lid in range(1, num + 1):
        cells     = np.argwhere(labeled == lid)
        size      = len(cells)
        depths    = mode_y - heightmap[cells[:, 0], cells[:, 1]]
        mean_depth = float(depths.mean())
        score     = size * mean_depth
        if score > best_score:
            best_score = score
            best_label = lid

    cells = np.argwhere(labeled == best_label)
    min_x = int(cells[:, 0].min())
    max_x = int(cells[:, 0].max())
    min_z = int(cells[:, 1].min())
    max_z = int(cells[:, 1].max())

    logger.info(
        "_detect_depression_rect: best component label=%d "
        "local dx=%d-%d dz=%d-%d (%dx%d blocks, %d cells, score=%.1f)",
        best_label, min_x, max_x, min_z, max_z,
        max_x - min_x + 1, max_z - min_z + 1,
        len(cells), best_score,
    )
    return Rect(
        (min_x, min_z),
        (max_x - min_x + 1, max_z - min_z + 1),
    )


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


# ---------------------------------------------------------------------------
# fill_depressions  (replaces fill_all_holes + seal_cave_openings)
# ---------------------------------------------------------------------------

def fill_depressions(
    editor:               Editor,
    analysis:             WorldAnalysisResult,
    depression_threshold: int = 3,
    border:               int = 2,
    slope_width:          int = 3,
    fill_block:           str = "minecraft:dirt",
    top_block:            str = "minecraft:grass_block",
) -> None:
    """
    Detect terrain depressions within best_area (expanded by `border` blocks
    on all sides) and fill them to the modal surface Y level, with sloped edges.

    Algorithm
    ---------
    1. Expand the search area by `border` blocks beyond best_area on all sides.
    2. Load a fresh heightmap for that expanded area.
    3. Compute modal Y of the expanded heightmap.
    4. Find all columns >= depression_threshold below modal Y.
    5. Compute their bounding rectangle.
    6. Fill that rectangle upward to modal Y — never carving.
       Edge columns are tapered over `slope_width` blocks for a natural ramp.
       Water columns (fountains etc.) are treated as empty space.

    Parameters
    ----------
    editor               : GDPC Editor
    analysis             : WorldAnalysisResult — heightmap_ground updated in-place
    depression_threshold : min deficit below modal Y to flag as depression (default 3)
    border               : blocks to expand search beyond best_area on each side (default 2)
    slope_width          : blocks over which fill tapers at the rect edges (default 3)
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
    hm_raw      = world_slice.heightmaps["MOTION_BLOCKING_NO_LEAVES"]
    heightmap   = np.array(hm_raw, dtype=np.int32) - 1

    mode = _modal_y(heightmap)
    logger.info("fill_depressions: modal Y=%d (search expanded by %d)", mode, border)

    depression_local = _detect_depression_rect(heightmap, mode, depression_threshold)
    if depression_local is None:
        logger.info("fill_depressions: no depressions found.")
        return

    # Convert local depression rect → world coordinates
    world_rect = Rect(
        (search_rect.offset.x + depression_local.offset.x,
         search_rect.offset.y + depression_local.offset.y),
        depression_local.size,
    )

    x0 = depression_local.offset.x
    z0 = depression_local.offset.y
    w  = depression_local.size.x
    d  = depression_local.size.y
    local_hm = heightmap[x0:x0 + w, z0:z0 + d].copy()

    _fill_rect(editor, world_rect, local_hm, mode, fill_block, top_block, slope_width)

    # Write filled heights back into analysis heightmap where they overlap best_area
    for dx in range(w):
        for dz in range(d):
            wx = world_rect.offset.x + dx
            wz = world_rect.offset.y + dz
            if area.contains_xz(wx, wz):
                ix = wx - area.x_from
                iz = wz - area.z_from
                analysis.heightmap_ground[ix, iz] = local_hm[dx, dz]

    logger.info("fill_depressions: done.")


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
# clear_area  (from terrain_clearer)
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
# remove_sparse_top  (from terrain_clearer)
# ---------------------------------------------------------------------------

def remove_sparse_top(
    editor:                    Editor,
    analysis:                  WorldAnalysisResult,
    districts:                 Districts | None = None,
    settlement_config:         SettlementConfig | None = None,
    sparse_threshold:          float = 0.08,
    min_height_above_dominant: int   = 3,
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
       c) bounding box fits the district-specific plot + buffer  (buildable)
       d) any non-natural block found in the cluster  (player structure)
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

    # Step 1: find dominant height level
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
                    submap[cx, cz] = target_y
                else:
                    positions = [(wx, wy, wz) for wy in range(dominant_y + 1, current_y + 1)]
                    if positions:
                        editor.placeBlock(positions, Block("minecraft:air"))
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
# fill_below_surface  (from terrain_clearer)
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
) -> None:
    """
    Recompute all derived terrain maps from the current world state after
    any terraforming operations.

    Updated maps
    ------------
    heightmap_ground      : re-sampled from world via MOTION_BLOCKING_NO_LEAVES
    heightmap_surface     : re-sampled from world via MOTION_BLOCKING
    water_mask            : derived from heightmap_surface != heightmap_ocean_floor
    water_distances       : distance transform from updated water_mask
    slope_map             : recomputed from updated heightmap_ground
    roughness_map         : recomputed from updated heightmap_ground
    plant_thickness       : recomputed from updated surface - ground heightmaps

    heightmap_ocean_floor and biomes are not modified by terraforming so are
    left unchanged.

    Parameters
    ----------
    editor   : GDPC Editor
    analysis : WorldAnalysisResult — all maps updated in-place
    config   : TerrainConfig — provides radius for roughness window
    """
    from scipy.ndimage import (
        distance_transform_edt,
        maximum_filter,
        minimum_filter,
    )
    from gdpc.vector_tools import Rect

    area = analysis.best_area

    # --- re-sample heightmaps from the world ---
    rect        = Rect((area.x_from, area.z_from), (area.width, area.depth))
    world_slice = editor.loadWorldSlice(rect, cache=False)  # cache=False forces fresh data

    hm_ground  = np.array(
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