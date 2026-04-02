from __future__ import annotations

import numpy as np
import logging
from scipy.ndimage import label as ndimage_label
from gdpc import Block
from gdpc.editor import Editor
from data.configurations import TerrainConfig, SettlementConfig
from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Districts, Plot

logger = logging.getLogger(__name__)

def clear_area(
    editor: Editor,
    analysis: WorldAnalysisResult,
    plot: Plot,
    config: TerrainConfig,
    buffer: int = 3,
) -> None:
    """
    Clear vegetation in a circular area around a plot.

    Iterates over cells within a circle of radius = max(width, depth)//2 + buffer
    and replaces any vegetation blocks with air.

    Args:
        editor: GDPC Editor instance.
        analysis: World analysis result containing heightmaps.
        plot: The plot to clear around.
        config: Terrain configuration (provides vegetation_block_keywords).
        buffer: Extra blocks of clearance radius beyond the plot bounds.

    Note
    ----
    Wrap calls in editor.pushBuffer()/popBuffer() to batch placements.
    """
    # Use center_x / center_z from RectangularArea base class
    center_x = int(plot.center_x)
    center_z = int(plot.center_z)

    radius    = max(plot.width, plot.depth) // 2 + buffer
    radius_sq = radius ** 2

    h_shape  = analysis.heightmap_ground.shape
    keywords = config.vegetation_block_keywords

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


# Natural terrain block IDs — only these are safe to remove.
# Anything else (planks, bricks, glass, etc.) indicates a player-built structure.
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
    """Return True if block_id belongs to natural terrain (safe to remove/replace)."""
    bid = block_id.lower()
    # Also accept ore blocks, stone variants, and generic suffixes
    return bid in _NATURAL_BLOCKS or any(
        bid.endswith(suffix) for suffix in (
            "_ore", "_stone", "_dirt", "_sand", "_gravel",
            "_leaves", "_log", "_wood", "_sapling",
        )
    )


def remove_sparse_top(
    editor: Editor,
    analysis: WorldAnalysisResult,
    districts: Districts | None = None,
    settlement_config: SettlementConfig | None = None,
    sparse_threshold: float = 0.08,
    min_height_above_dominant: int = 5,
    max_height_above_dominant: int = 12,
    max_terrain_std: float = 12.0,
    building_buffer: int = 2,
    edge_buffer: int = 1,
    slope_width: int = 2,
    max_aspect_ratio: float = 3.0,
    gap_block_samples: int = 10,
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
    4. For each candidate cluster:
       - Compute per-cell distance-to-edge (distance transform on cluster mask).
       - Cells within edge_buffer distance: untouched (natural buffer).
       - Cells within edge_buffer + slope_width: shaved to intermediate height
         (creates a slope rather than a cliff).
       - Interior cells: removed to dominant_y.
       - Each block is checked against _NATURAL_BLOCKS before removal — any
         non-natural block (structure) causes the entire cluster to be skipped.
    5. Narrow stripe shaving and enclosed gap filling follow (steps 4 & 5 below).

    Args:
        editor: GDPC Editor instance.
        analysis: World analysis result (heightmap_ground updated in-place).
        districts: Districts for per-district plot size lookup.
        settlement_config: Provides plot_width / plot_depth per district type.
        sparse_threshold: Max cluster area fraction of dominant patch (default 0.08).
        min_height_above_dominant: Minimum Y difference for a cluster to be removed
                                   (default 3 — ignore 1-2 block bumps).
        building_buffer: Extra cells around plot footprint for buildability check.
        edge_buffer: Cells at the cluster edge left completely untouched (default 1).
        slope_width: Cells beyond edge_buffer that are tapered down gradually (default 2).
        max_aspect_ratio: Aspect ratio above which a cluster is a narrow stripe.
        gap_block_samples: Cells sampled to determine gap fill block.
    """
    area   = analysis.best_area
    submap = analysis.heightmap_ground.copy()
    w, d   = submap.shape
    ix0 = iz0 = 0   # submap[cx, cz] → world (area.x_from + cx, area.z_from + cz)

    # Early exit: if the terrain is highly irregular (mountains, cliffs, snowy
    # peaks) the per-height-level cluster approach would shave the entire
    # mountain down to the valley floor.  Skip in that case.
    terrain_std = float(np.std(submap))
    if terrain_std > max_terrain_std:
        logger.info(
            "remove_sparse_top: terrain std=%.1f > %.1f — skipping (mountainous area).",
            terrain_std, max_terrain_std,
        )
        return

    # ------------------------------------------------------------------
    # Step 1: find dominant height level
    # ------------------------------------------------------------------
    # For each unique Y value, label contiguous flat patches (cells == Y)
    # and record the size of the largest patch.  The Y with the biggest
    # largest-patch wins.
    unique_heights = np.unique(submap)
    dominant_y     = int(unique_heights[0])
    dominant_area  = 0

    # Also store: for each height, list of (labeled_array, cluster_sizes)
    # so we don't recompute below.
    height_clusters: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for y in unique_heights:
        flat_mask          = (submap == y)
        labeled, num       = ndimage_label(flat_mask)
        if num == 0:
            continue
        sizes              = np.bincount(labeled.ravel())[1:]  # skip background
        height_clusters[int(y)] = (labeled, sizes)
        largest            = int(sizes.max())
        if largest > dominant_area:
            dominant_area  = largest
            dominant_y     = int(y)

    if dominant_area == 0:
        return

    sparse_limit = sparse_threshold * dominant_area

    # Build a helper that returns the minimum buildable bounding-box dimensions
    # for a given local (cx, cz) index, using that cell's district type.
    # Falls back to global max if districts or settlement_config is unavailable.
    _fallback_w = _fallback_d = 8
    if settlement_config is not None:
        _fallback_w = max(settlement_config.plot_width.values(),  default=8)
        _fallback_d = max(settlement_config.plot_depth.values(),  default=8)

    def _min_buildable(cx: int, cz: int) -> tuple[int, int]:
        """Return (min_w, min_d) required to preserve a cluster centred near (cx, cz)."""
        if districts is None or settlement_config is None:
            return _fallback_w + 2 * building_buffer, _fallback_d + 2 * building_buffer

        # submap indices are already aligned with the district map
        dm_x = cx
        dm_z = cz

        if not (0 <= dm_x < districts.map.shape[0] and
                0 <= dm_z < districts.map.shape[1]):
            return _fallback_w + 2 * building_buffer, _fallback_d + 2 * building_buffer

        district_idx  = int(districts.map[dm_x, dm_z])
        dtype         = districts.types.get(district_idx, "residential")
        plot_w        = settlement_config.plot_width.get(dtype, _fallback_w)
        plot_d        = settlement_config.plot_depth.get(dtype, _fallback_d)
        return plot_w + 2 * building_buffer, plot_d + 2 * building_buffer

    # ------------------------------------------------------------------
    # Step 2 & 3: for each level above dominant, remove sparse clusters
    # ------------------------------------------------------------------
    for y in unique_heights:
        y = int(y)
        if y <= dominant_y:
            continue   # only remove things above the dominant level
        if y - dominant_y > max_height_above_dominant:
            continue   # too high above dominant — part of real terrain, not a blob

        labeled, sizes = height_clusters.get(y, (None, None))
        if labeled is None:
            continue

        label_ids  = np.arange(1, len(sizes) + 1)
        sparse_ids = label_ids[sizes < sparse_limit]

        for lid in sparse_ids:
            cells = np.argwhere(labeled == lid)

            # Keep clusters whose bounding box could fit the district-specific
            # building footprint + buffer.  Use the cluster centroid to look up
            # which district this cluster falls in.
            bb_w      = int(cells[:, 0].max() - cells[:, 0].min() + 1)
            bb_d      = int(cells[:, 1].max() - cells[:, 1].min() + 1)
            centroid_x = int(cells[:, 0].mean())
            centroid_z = int(cells[:, 1].mean())
            min_w, min_d = _min_buildable(centroid_x, centroid_z)
            if bb_w >= min_w and bb_d >= min_d:
                continue

            # --- structure check ---
            # Sample every cell in the cluster. If any non-natural block is found,
            # skip the entire cluster to avoid destroying player-built structures.
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

            # --- height guard ---
            # Skip clusters that are only min_height_above_dominant or less
            # above dominant — shallow bumps should be left alone.
            cluster_heights = np.array([int(submap[int(cx), int(cz)]) for cx, cz in cells])
            if int(cluster_heights.max()) - dominant_y < min_height_above_dominant:
                continue

            # --- distance-to-edge map for buffer + slope ---
            from scipy.ndimage import distance_transform_edt
            cluster_mask_local = np.zeros((w, d), dtype=bool)
            for cx, cz in cells:
                cluster_mask_local[int(cx), int(cz)] = True
            # Distance of each cluster cell from the nearest non-cluster cell
            dist_map = distance_transform_edt(cluster_mask_local)

            for cx, cz in cells:
                cx, cz    = int(cx), int(cz)
                cell_dist = float(dist_map[cx, cz])
                current_y = int(submap[cx, cz])
                wx, wz    = area.index_to_world(cx, cz)

                if cell_dist <= edge_buffer:
                    continue

                elif cell_dist <= edge_buffer + slope_width:
                    slope_t   = (cell_dist - edge_buffer) / slope_width
                    target_y  = int(current_y - slope_t * (current_y - dominant_y))
                    target_y  = max(target_y, dominant_y)
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

    # ------------------------------------------------------------------
    # Step 4: shave narrow stripes above dominant level
    # ------------------------------------------------------------------
    # A cluster is a narrow stripe if its bounding-box aspect ratio exceeds
    # max_aspect_ratio (default 3:1).  Shave one layer at a time until the
    # cluster is no longer narrow or reaches dominant_y.
    # Re-label at the current submap state so previously removed cells don't
    # inflate cluster sizes.
    current_submap = submap.copy()

    any_changed = True
    while any_changed:
        any_changed = False
        unique_now = np.unique(current_submap)

        for y in unique_now:
            y = int(y)
            if y <= dominant_y:
                continue
            if y - dominant_y > max_height_above_dominant:
                continue   # never shave real mountain terrain

            flat_mask      = (current_submap == y)
            labeled, num   = ndimage_label(flat_mask)
            if num == 0:
                continue
            sizes          = np.bincount(labeled.ravel())[1:]
            label_ids      = np.arange(1, len(sizes) + 1)

            for lid in label_ids:
                cells  = np.argwhere(labeled == lid)
                bb_w   = int(cells[:, 0].max() - cells[:, 0].min() + 1)
                bb_d   = int(cells[:, 1].max() - cells[:, 1].min() + 1)

                short  = min(bb_w, bb_d)
                long_  = max(bb_w, bb_d)
                if short == 0:
                    continue
                ratio  = long_ / short

                if ratio <= max_aspect_ratio:
                    continue  # not narrow

                for cx, cz in cells:
                    cx, cz = int(cx), int(cz)
                    wx, wz = area.index_to_world(cx, cz)
                    editor.placeBlock((wx, y, wz), Block("minecraft:air"))
                    editor.placeBlock((wx, y - 1, wz), Block("minecraft:grass_block"))
                    current_submap[cx, cz] = y - 1
                    submap[cx, cz]         = y - 1

                any_changed = True

    # ------------------------------------------------------------------
    # Step 5: fill enclosed gaps below dominant level
    # ------------------------------------------------------------------
    # A gap is a cell below dominant_y where ALL 4 cardinal neighbours are
    # at dominant_y (fully enclosed depression).
    # Fill from gap_height+1 to dominant_y with the dominant-level block.

    # Sample the most common block at dominant_y from up to `gap_block_samples`
    # cells at that level, then use that block ID for filling.
    dominant_cells = np.argwhere(submap == dominant_y)
    fill_block_id  = "minecraft:dirt"  # safe fallback

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

    fill_block = Block(fill_block_id)

    # Detect enclosed gaps: cells below dominant_y fully surrounded by dominant_y
    gap_mask = np.zeros((w, d), dtype=bool)
    interior = np.s_[1:-1, 1:-1]

    below_dominant = (submap < dominant_y)
    at_dominant    = (submap == dominant_y)

    # A cell is a gap if it is below dominant AND at least 3 of its 4 cardinal
    # neighbours are at or above dominant. The original "all 4" requirement was
    # too strict — natural terrain almost never satisfies it, so nearly all
    # holes were silently skipped.
    neighbour_count = (
        at_dominant[2:,   1:-1].astype(np.int8) +
        at_dominant[:-2,  1:-1].astype(np.int8) +
        at_dominant[1:-1, 2:  ].astype(np.int8) +
        at_dominant[1:-1, :-2 ].astype(np.int8)
    )
    gap_mask[interior] = below_dominant[1:-1, 1:-1] & (neighbour_count >= 3)

    gap_cells = np.argwhere(gap_mask)
    for cx, cz in gap_cells:
        cx, cz    = int(cx), int(cz)
        wx, wz    = area.index_to_world(cx, cz)
        gap_y     = int(submap[cx, cz])

        # Fill from gap_y+1 up to dominant_y (inclusive)
        positions = [(wx, wy, wz) for wy in range(gap_y + 1, dominant_y + 1)]
        if positions:
            editor.placeBlock(positions, fill_block)

        submap[cx, cz] = dominant_y

    # Write the cleaned heightmap back into the analysis result
    analysis.heightmap_ground[:, :] = submap


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

    # --- Pass A: detect from surface_blocks ---
    lava_mask = np.vectorize(
        lambda b: "lava" in str(b).lower()
    )(analysis.surface_blocks).astype(bool)

    # --- Pass B: probe fluid cells that surface_blocks missed ---
    # water_mask is True for any fluid (water OR lava).  Check actual block
    # for cells that surface_blocks doesn't already mark as lava.
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

    # Pre-compute fill heights: median of surrounding non-lava neighbours.
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

        # Fill from 6 blocks below lava surface up to fill_top with stone
        # so lava cannot re-flow.  Stone is cheaper than dirt for the server
        # and won't be confused with surface soil.
        fill_range = range(cell_y - 6, fill_top)
        if fill_range:
            editor.placeBlock(
                [(wx, wy, wz) for wy in fill_range],
                Block("minecraft:stone"),
            )
        editor.placeBlock((wx, fill_top, wz), Block("minecraft:grass_block"))

        heightmap[ix, iz] = fill_top


