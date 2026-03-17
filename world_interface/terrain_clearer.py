from __future__ import annotations

import numpy as np
from scipy.ndimage import label as ndimage_label
from gdpc import Block
from gdpc.editor import Editor
from data.configurations import TerrainConfig, SettlementConfig
from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Districts, Plot


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


def remove_sparse_top(
    editor: Editor,
    analysis: WorldAnalysisResult,
    districts: Districts | None = None,
    settlement_config: SettlementConfig | None = None,
    sparse_threshold: float = 0.15,
    building_buffer: int = 2,
    max_aspect_ratio: float = 3.0,
    gap_block_samples: int = 10,
) -> None:
    """
    Remove clusters that are too small relative to the dominant flat level,
    but preserve any cluster large enough to fit a building for its district.

    Algorithm
    ---------
    1. Find the dominant height level: the Y value whose contiguous flat patch
       covers the most total area (largest connected component of cells at that Y).
    2. For every height level ABOVE the dominant level, find all contiguous
       clusters of cells at that height.
    3. A cluster is a candidate for removal if BOTH conditions hold:
       a) Its area is less than `sparse_threshold` × dominant_patch_area (15% default).
       b) Its bounding box cannot fit the plot size of its specific district
          (looked up via the Voronoi district map) + `building_buffer` on each side.
          If districts is None, falls back to the largest plot size across all types.
    4. Candidates are removed down to the dominant level (air + heightmap update).
    5. Narrow stripes (bounding-box aspect ratio > max_aspect_ratio) are shaved one
       layer at a time until no longer narrow or dominant level is reached.
    6. Enclosed gaps (cells below dominant_y with all 4 neighbours at dominant_y) are
       filled up to dominant level using the most common block sampled at that level.

    Args:
        editor: GDPC Editor instance.
        analysis: World analysis result (heightmap_ground updated in-place).
        districts: Districts object from the planner, used to look up per-district
                   plot sizes. If None, uses the global maximum plot size as fallback.
        settlement_config: Provides plot_width / plot_depth per district type.
        sparse_threshold: Max cluster area as fraction of dominant patch before
                          removal is considered (default 0.15 = 15%).
        building_buffer: Extra cells of clearance around the plot footprint (default 2).
        max_aspect_ratio: Bounding-box long:short ratio above which a cluster is
                          considered a narrow stripe and shaved down (default 3.0).
        gap_block_samples: Number of dominant-level cells sampled to determine the
                           most common fill block for gap filling (default 10).
    """
    area   = analysis.best_area
    # Work directly on the full heightmap — it is already sized to best_area.
    # ix0/iz0 are always (0,0) since the heightmap is indexed relative to best_area,
    # so we skip the world_to_index call and use simple offsets for world conversion.
    submap = analysis.heightmap_ground.copy()
    w, d   = submap.shape
    ix0 = iz0 = 0   # submap[cx, cz] → world (area.x_from + cx, area.z_from + cz)

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

            for cx, cz in cells:
                cx, cz = int(cx), int(cz)
                wx, wz = area.index_to_world(cx, cz)

                # Remove every block from current cluster height down to dominant_y+1
                current_y = int(submap[cx, cz])
                positions = [(wx, wy, wz) for wy in range(dominant_y + 1, current_y + 1)]
                if positions:
                    editor.placeBlock(positions, Block("minecraft:air"))

                # Update submap and source heightmap
                submap[cx, cz]                          = dominant_y
                submap[cx, cz]           = dominant_y

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

                # Narrow stripe — shave this layer (set to y-1, place air at y)
                for cx, cz in cells:
                    cx, cz = int(cx), int(cz)
                    wx, wz = area.index_to_world(cx, cz)
                    editor.placeBlock((wx, y, wz), Block("minecraft:air"))
                    current_submap[cx, cz]            = y - 1
                    submap[cx, cz]                    = y - 1
                    submap[cx, cz]     = y - 1

                any_changed = True  # re-run to check if still narrow after shave

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

    # A cell is enclosed if it is below dominant AND all 4 neighbours are at dominant
    gap_mask[interior] = (
        below_dominant[1:-1, 1:-1] &
        at_dominant[2:,   1:-1] &   # south neighbour
        at_dominant[:-2,  1:-1] &   # north neighbour
        at_dominant[1:-1, 2:  ] &   # east neighbour
        at_dominant[1:-1, :-2 ]     # west neighbour
    )

    gap_cells = np.argwhere(gap_mask)
    for cx, cz in gap_cells:
        cx, cz    = int(cx), int(cz)
        wx, wz    = area.index_to_world(cx, cz)
        gap_y     = int(submap[cx, cz])

        # Fill from gap_y+1 up to dominant_y (inclusive)
        positions = [(wx, wy, wz) for wy in range(gap_y + 1, dominant_y + 1)]
        if positions:
            editor.placeBlock(positions, fill_block)

        submap[cx, cz]                      = dominant_y
        submap[cx, cz]       = dominant_y

    # Write the cleaned heightmap back into the analysis result
    analysis.heightmap_ground[:, :] = submap