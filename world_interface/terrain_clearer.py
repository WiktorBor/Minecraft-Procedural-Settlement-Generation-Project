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
    min_height_above_dominant: int = 3,
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
                    # Natural buffer — leave untouched
                    continue

                elif cell_dist <= edge_buffer + slope_width:
                    # Slope zone — remove proportionally fewer layers
                    # Cells closer to edge get shaved less; interior cells more.
                    slope_t   = (cell_dist - edge_buffer) / slope_width  # 0→1
                    target_y  = int(current_y - slope_t * (current_y - dominant_y))
                    target_y  = max(target_y, dominant_y)
                    positions = [(wx, wy, wz) for wy in range(target_y + 1, current_y + 1)]
                    if positions:
                        editor.placeBlock(positions, Block("minecraft:air"))
                    submap[cx, cz] = target_y

                else:
                    # Interior — remove fully to dominant_y
                    positions = [(wx, wy, wz) for wy in range(dominant_y + 1, current_y + 1)]
                    if positions:
                        editor.placeBlock(positions, Block("minecraft:air"))
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

        submap[cx, cz] = dominant_y

    # Write the cleaned heightmap back into the analysis result
    analysis.heightmap_ground[:, :] = submap


def fill_below_surface(
    editor: Editor,
    analysis: WorldAnalysisResult,
    target_height: int,
    sample_radius: int = 3,
) -> None:
    """
    Fill all cells below `target_height` using blocks sampled from neighbouring
    surface cells, weighted by inverse distance.

    For each cell whose heightmap value is below `target_height`, the method
    samples surface blocks from a square neighbourhood of `sample_radius` cells.
    Each neighbour contributes weight = 1 / distance, so closer neighbours
    influence the block choice more strongly.  The block with the highest total
    weight is used to fill from the cell's current surface up to `target_height`.

    The heightmap is updated in-place so subsequent planning sees correct heights.

    Args:
        editor: GDPC Editor instance (buffering=True recommended).
        analysis: WorldAnalysisResult — heightmap_ground updated in-place.
        target_height: Y level to fill up to (inclusive).
        sample_radius: Chebyshev radius of the neighbourhood to sample (default 3).
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground
    w, d      = heightmap.shape

    # Pre-build offset grid with inverse-distance weights (exclude centre cell).
    offsets: list[tuple[int, int, float]] = []
    for dx in range(-sample_radius, sample_radius + 1):
        for dz in range(-sample_radius, sample_radius + 1):
            if dx == 0 and dz == 0:
                continue
            dist = (dx * dx + dz * dz) ** 0.5
            offsets.append((dx, dz, 1.0 / dist))

    # Find all cells below target_height
    below_mask = heightmap < target_height
    cells      = np.argwhere(below_mask)

    if len(cells) == 0:
        return

    for cx, cz in cells:
        cx, cz    = int(cx), int(cz)
        cell_y    = int(heightmap[cx, cz])

        if cell_y >= target_height:
            continue

        # ------------------------------------------------------------------
        # Sample neighbours — weighted by inverse distance
        # ------------------------------------------------------------------
        block_weights: dict[str, float] = {}

        for dx, dz, weight in offsets:
            nx, nz = cx + dx, cz + dz
            if not (0 <= nx < w and 0 <= nz < d):
                continue

            neighbour_y = int(heightmap[nx, nz])
            # Only sample neighbours that are at or above target to get
            # representative surface blocks, not other below-target cells.
            if neighbour_y < target_height:
                continue

            wx, wz  = area.index_to_world(nx, nz)
            block   = editor.getBlock((wx, neighbour_y, wz))
            bid     = block.id.lower()

            if not bid or bid == "minecraft:air":
                continue

            block_weights[bid] = block_weights.get(bid, 0.0) + weight

        if not block_weights:
            # No valid neighbours found — skip this cell
            continue

        # Most common block by weighted vote
        fill_id    = max(block_weights, key=block_weights.get)
        fill_block = Block(fill_id)

        # ------------------------------------------------------------------
        # Fill from cell_y+1 up to target_height (inclusive)
        # ------------------------------------------------------------------
        wx, wz    = area.index_to_world(cx, cz)
        positions = [(wx, wy, wz) for wy in range(cell_y + 1, target_height + 1)]
        if positions:
            editor.placeBlock(positions, fill_block)

        # Update heightmap
        heightmap[cx, cz] = target_height


def seal_cave_openings(
    editor: Editor,
    analysis: WorldAnalysisResult,
    drop_threshold: int = 3,
    fill_depth: int = 4,
    sample_radius: int = 3,
) -> None:
    """
    Detect and seal cave openings / sinkholes in the terrain.

    A hole is defined as a cell whose surface height is more than
    `drop_threshold` blocks below at least one of its 4 cardinal neighbours.
    Connected hole cells are grouped, then each group is filled to the lowest
    height found on the rim (the non-hole neighbours bordering the group).

    Fill strategy (simulates human terraforming):
    - Subsurface layers: filled solid using the most common subsurface block
      sampled from rim neighbours at one block below their surface, weighted
      by inverse distance.  Up to `fill_depth - 1` layers.
    - Cap layer: the top block uses the most common surface block sampled from
      rim neighbours at their surface height, weighted by inverse distance.
      This ensures grass caps grass holes, sand caps sand holes, etc.
    - The heightmap is updated in-place.

    Args:
        editor: GDPC Editor instance (buffering=True recommended).
        analysis: WorldAnalysisResult — heightmap_ground updated in-place.
        drop_threshold: Minimum height difference to a neighbour before a cell
                        is considered a hole (default 3 blocks).
        fill_depth: How many blocks deep to fill solidly before placing the
                    surface cap (default 4, so 3 subsurface + 1 cap).
        sample_radius: Chebyshev radius used when sampling rim blocks for fill
                       block selection (default 3).
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground
    w, d      = heightmap.shape

    # ------------------------------------------------------------------
    # Step 1: detect hole cells — drop > threshold vs any cardinal neighbour
    # ------------------------------------------------------------------
    h = heightmap.astype(np.float32)

    # Max height of the 4 cardinal neighbours (edge cells use the cell itself)
    neighbour_max = np.full((w, d), -np.inf, dtype=np.float32)
    neighbour_max[:-1, :] = np.maximum(neighbour_max[:-1, :], h[1:,  :])
    neighbour_max[1:,  :] = np.maximum(neighbour_max[1:,  :], h[:-1, :])
    neighbour_max[:,  :-1] = np.maximum(neighbour_max[:, :-1], h[:,  1:])
    neighbour_max[:,   1:] = np.maximum(neighbour_max[:,  1:], h[:,  :-1])

    # Clamp edge cells that have no neighbour on one side
    neighbour_max = np.where(np.isinf(neighbour_max), h, neighbour_max)

    hole_mask = (neighbour_max - h) >= drop_threshold

    if not np.any(hole_mask):
        return

    # ------------------------------------------------------------------
    # Step 2: group connected hole cells
    # ------------------------------------------------------------------
    labeled, num_holes = ndimage_label(hole_mask)
    if num_holes == 0:
        return

    # Pre-build inverse-distance offset grid (same pattern as fill_below_surface)
    offsets: list[tuple[int, int, float]] = []
    for dx in range(-sample_radius, sample_radius + 1):
        for dz in range(-sample_radius, sample_radius + 1):
            if dx == 0 and dz == 0:
                continue
            dist = (dx * dx + dz * dz) ** 0.5
            offsets.append((dx, dz, 1.0 / dist))

    # ------------------------------------------------------------------
    # Step 3: process each hole group
    # ------------------------------------------------------------------
    for hole_id in range(1, num_holes + 1):
        hole_cells = np.argwhere(labeled == hole_id)

        # Find rim cells: non-hole neighbours of any hole cell
        rim_set: set[tuple[int, int]] = set()
        for cx, cz in hole_cells:
            cx, cz = int(cx), int(cz)
            for dx, dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, nz = cx + dx, cz + dz
                if 0 <= nx < w and 0 <= nz < d and not hole_mask[nx, nz]:
                    rim_set.add((nx, nz))

        if not rim_set:
            continue

        # Target fill height = lowest rim neighbour surface
        target_y = min(int(heightmap[rx, rz]) for rx, rz in rim_set)

        # ------------------------------------------------------------------
        # Sample surface and subsurface blocks from rim, weighted by distance
        # ------------------------------------------------------------------
        # surface_weights: blocks at rim surface height (for the cap layer)
        # sub_weights:     blocks one below rim surface (for subsurface fill)
        surface_weights: dict[str, float] = {}
        sub_weights:     dict[str, float] = {}

        for cx, cz in hole_cells:
            cx, cz = int(cx), int(cz)

            for dx, dz, weight in offsets:
                nx, nz = cx + dx, cz + dz
                if not (0 <= nx < w and 0 <= nz < d):
                    continue
                if hole_mask[nx, nz]:
                    continue  # only sample from non-hole (rim/plateau) cells

                surf_y = int(heightmap[nx, nz])
                wx, wz = area.index_to_world(nx, nz)

                # Surface block (cap)
                blk = editor.getBlock((wx, surf_y, wz))
                bid = blk.id.lower()
                if bid and bid != "minecraft:air":
                    surface_weights[bid] = surface_weights.get(bid, 0.0) + weight

                # Subsurface block (fill body) — one below surface
                if surf_y - 1 >= 0:
                    blk_sub = editor.getBlock((wx, surf_y - 1, wz))
                    bid_sub = blk_sub.id.lower()
                    if bid_sub and bid_sub != "minecraft:air":
                        sub_weights[bid_sub] = sub_weights.get(bid_sub, 0.0) + weight

        surface_block = Block(max(surface_weights, key=surface_weights.get)
                              if surface_weights else "minecraft:grass_block")
        sub_block     = Block(max(sub_weights, key=sub_weights.get)
                              if sub_weights else "minecraft:dirt")

        # ------------------------------------------------------------------
        # Step 4: fill each hole cell
        # ------------------------------------------------------------------
        for cx, cz in hole_cells:
            cx, cz  = int(cx), int(cz)
            cell_y  = int(heightmap[cx, cz])
            wx, wz  = area.index_to_world(cx, cz)

            if cell_y >= target_y:
                continue

            # How deep to fill solidly: up to fill_depth blocks below target
            solid_from = max(cell_y + 1, target_y - fill_depth + 1)
            solid_to   = target_y - 1   # one below the cap

            # Subsurface fill (solid body)
            if solid_from <= solid_to:
                positions = [(wx, wy, wz) for wy in range(solid_from, solid_to + 1)]
                editor.placeBlock(positions, sub_block)

            # Cap layer (surface block)
            editor.placeBlock((wx, target_y, wz), surface_block)

            # Update heightmap
            heightmap[cx, cz] = target_y


def seal_cave_openings(
    editor: Editor,
    analysis: WorldAnalysisResult,
    detection_radius: int = 4,
    depth_threshold_std: float = 2.0,
    surface_sample_radius: int = 2,
) -> None:
    """
    Detect and seal cave openings / sinkholes in the terrain.

    Uses heightmap_ground to find cells that are anomalously deep compared
    to their local neighbourhood — the signature of a cave entrance or sinkhole
    rather than a natural slope.  The entire connected depression is flood-filled
    to blend with the surrounding terrain.

    Detection
    ---------
    For each cell, compute the mean and standard deviation of heightmap_ground
    within a `detection_radius` neighbourhood (via uniform_filter).  A cell is
    flagged as a hole if:
        cell_height < local_mean - depth_threshold_std * local_std

    This is adaptive — on flat terrain even a 3-block drop gets flagged, while
    on naturally rough terrain the threshold rises to avoid false positives.

    Fill strategy
    -------------
    1. Flood-fill each connected hole region to find the full depression extent.
    2. Compute the target fill height as the mean height of the hole's rim cells
       (the non-hole neighbours immediately surrounding the depression).
    3. Sample surface blocks from the rim using inverse-distance weighting —
       the most common weighted block becomes the cap (top layer).
    4. Fill from hole_bottom+1 to target_height-1 with minecraft:dirt, then
       place the sampled cap block at target_height.
    5. Update heightmap_ground in-place.

    Args:
        editor: GDPC Editor instance.
        analysis: WorldAnalysisResult — heightmap_ground updated in-place.
        detection_radius: Neighbourhood radius for local mean/std computation (default 4).
        depth_threshold_std: How many standard deviations below local mean a cell
                             must be to count as a hole (default 2.0).
        surface_sample_radius: Chebyshev radius around each rim cell to sample
                                surface blocks from (default 2).
    """
    from scipy.ndimage import uniform_filter

    area      = analysis.best_area
    heightmap = analysis.heightmap_ground.astype(np.float32)
    w, d      = heightmap.shape

    size = 2 * detection_radius + 1

    # ------------------------------------------------------------------
    # Step 1: compute local mean and std, detect hole cells
    # ------------------------------------------------------------------
    local_mean = uniform_filter(heightmap, size=size)
    # std = sqrt(E[x²] - E[x]²)
    local_std  = np.sqrt(
        np.maximum(
            uniform_filter(heightmap ** 2, size=size) - local_mean ** 2,
            0.0,
        )
    )

    hole_mask = heightmap < (local_mean - depth_threshold_std * local_std)

    if not np.any(hole_mask):
        return

    # ------------------------------------------------------------------
    # Step 2: flood-fill connected hole regions
    # ------------------------------------------------------------------
    from scipy.ndimage import label as ndimage_label
    labeled, num_holes = ndimage_label(hole_mask)

    if num_holes == 0:
        return

    for hole_id in range(1, num_holes + 1):
        hole_cells = np.argwhere(labeled == hole_id)

        # ------------------------------------------------------------------
        # Step 3: find the rim — non-hole cells directly adjacent to this hole
        # ------------------------------------------------------------------
        rim_set: set[tuple[int, int]] = set()
        for cx, cz in hole_cells:
            cx, cz = int(cx), int(cz)
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = cx + dx, cz + dz
                if 0 <= nx < w and 0 <= nz < d and not hole_mask[nx, nz]:
                    rim_set.add((nx, nz))

        if not rim_set:
            continue

        rim_cells  = np.array(list(rim_set))
        target_y   = int(np.mean(heightmap[rim_cells[:, 0], rim_cells[:, 1]]))

        # ------------------------------------------------------------------
        # Step 4: sample surface blocks from the rim (inverse-distance weighted)
        # ------------------------------------------------------------------
        block_weights: dict[str, float] = {}

        for rx, rz in rim_set:
            for dx in range(-surface_sample_radius, surface_sample_radius + 1):
                for dz in range(-surface_sample_radius, surface_sample_radius + 1):
                    nx, nz = rx + dx, rz + dz
                    if not (0 <= nx < w and 0 <= nz < d):
                        continue
                    if hole_mask[nx, nz]:
                        continue  # don't sample from inside the hole

                    dist = max((dx * dx + dz * dz) ** 0.5, 0.01)
                    weight = 1.0 / dist

                    surf_y  = int(heightmap[nx, nz])
                    wx, wz  = area.index_to_world(nx, nz)
                    block   = editor.getBlock((wx, surf_y, wz))
                    bid     = block.id.lower()

                    if bid and bid != "minecraft:air":
                        block_weights[bid] = block_weights.get(bid, 0.0) + weight

        cap_block_id = (
            max(block_weights, key=block_weights.get)
            if block_weights else "minecraft:dirt"
        )

        # ------------------------------------------------------------------
        # Step 5: fill each hole cell
        # ------------------------------------------------------------------
        for cx, cz in hole_cells:
            cx, cz  = int(cx), int(cz)
            hole_y  = int(heightmap[cx, cz])
            wx, wz  = area.index_to_world(cx, cz)

            if hole_y >= target_y:
                continue

            # Fill with dirt from hole bottom up to target_y - 1
            dirt_positions = [
                (wx, wy, wz)
                for wy in range(hole_y + 1, target_y)
            ]
            if dirt_positions:
                editor.placeBlock(dirt_positions, Block("minecraft:dirt"))

            # Cap with the sampled surface block at target_y
            editor.placeBlock((wx, target_y, wz), Block(cap_block_id))

            # Update heightmap
            analysis.heightmap_ground[cx, cz] = target_y