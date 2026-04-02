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

Call order in settlement_generator.py Phase 2
----------------------------------------------
    remove_sparse_top(...)    # terrain_clearer
    terraform_area(...)       # smooth bumps downward (no plots)
    clear_lava_pools(...)     # terrain_clearer — clear surface lava
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

import numpy as np
from gdpc import Block
from gdpc.editor import Editor
from scipy.ndimage import binary_closing, uniform_filter

from data.analysis_results import WorldAnalysisResult
from data.build_area import BuildArea
from data.configurations import SettlementConfig
from data.settlement_entities import Plot

logger = logging.getLogger(__name__)

_AIR_IDS: frozenset[str] = frozenset({
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
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
        raising anything.  Each pass moves cells above the local mean down
        by up to ``max_change_per_pass`` blocks.

    **Platform mode** (``plots`` provided):
        Additive-only fill.  Raises every allowed column inside best_area
        to ``target_y = min(plot.y)`` so structures have a solid base.
        When ``outer_blend_width > 0`` the fill extends outside best_area
        in a band that steps down 1 block per cell, creating a natural slope.
        Optionally fills voids directly under plot floors (``fill_plot_support``).

    Legacy kwargs (``wall_padding``, ``edge_blend_width``, …) are silently
    discarded via ``**kwargs``.
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

    Each pass:
      1. Compute the neighbourhood mean via uniform_filter.
      2. For cells ABOVE the mean by at least min_shave_blocks: move down by up
         to max_change_per_pass.  Gentle variations (< min_shave_blocks) are
         left untouched so nearly-flat terrain is never needlessly disturbed.
      3. For cells BELOW the mean: leave untouched.

    Snow-covered cells are skipped entirely — shaving a snow layer off exposes
    the grass or stone underneath and looks wrong.
    """
    area           = analysis.best_area
    heightmap      = analysis.heightmap_ground.astype(np.float32)
    w, d           = heightmap.shape
    size           = 2 * smooth_radius + 1
    surface_blocks = analysis.surface_blocks

    # Build a per-cell "safe to shave" mask: skip water and snow-covered cells.
    snow_mask = np.vectorize(
        lambda b: "snow" in str(b).lower()
    )(surface_blocks).astype(bool)
    skip_mask = analysis.water_mask.astype(bool) | snow_mask

    for _ in range(passes):
        local_mean  = uniform_filter(heightmap, size=size, mode="nearest")
        excess      = heightmap - local_mean          # positive = above mean
        # Only shave where the cell is meaningfully above the local average.
        apply_mask  = (excess >= min_shave_blocks) & ~skip_mask
        delta       = np.where(apply_mask, np.clip(-excess, -max_change_per_pass, 0.0), 0.0)
        heightmap   = heightmap + delta

    new_heights = np.round(heightmap).astype(np.int32)
    old_heights = analysis.heightmap_ground.astype(np.int32)

    # Block IDs whose newly-exposed top should be re-skinned as grass_block.
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

            # Re-skin only for grass/dirt surfaces (not snow, stone, sand, …).
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

    # ---- footings: fill voids directly under each plot floor ----
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

    # ---- build the fill mask ----
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

    # ---- interior fill: every allowed cell raised to target_y ----
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

    # ---- outer blend: step down 1 block per cell beyond best_area ----
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
    sits on flat ground.

    For each wall side:
      1. Sample all heights along the wall line.
      2. Compute the median.
      3. Fill upward or cut downward to that median height.

    Call this AFTER terraform_area, just before FortificationBuilder.build().
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

# (hole/cave filling removed — lava pools are handled by clear_lava_pools in terrain_clearer)
