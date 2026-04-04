"""
debug/test_heightmap_verify.py
-------------------------------
Verifies that fill_depressions correctly updates analysis.heightmap_ground
by comparing the in-memory map against a freshly fetched heightmap from
Minecraft after the blocks have been flushed.

Output
------
  - Number of cells that differ between the two maps
  - Max / mean / median absolute difference
  - List of the top-10 worst mismatches (world x, z, in-memory Y, fetched Y)
  - Whether the in-memory map is consistently lower, higher, or mixed

Run with:  python -m debug.test_heightmap_verify
"""
from __future__ import annotations

import logging
import sys

import matplotlib.pyplot as plt
import numpy as np
from gdpc import Editor

from analysis.world_analysis import WorldAnalyser
from data.configurations import TerrainConfig
from utils.http_client import GDMCClient
from world_interface.terrain_loader import TerrainLoader
from world_interface.terraforming import fill_depressions, refresh_ground_heightmap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    client = GDMCClient()
    if not client.check_connection():
        logger.error("Could not connect to GDMC HTTP Interface. Is Minecraft running?")
        return 1

    logger.info("Connection OK.")

    editor         = Editor(buffering=True)
    terrain_config = TerrainConfig()
    terrain_loader = TerrainLoader(client)

    # --- Phase 0: World analysis ---
    logger.info("[Phase 0] Analysing world...")
    analyser = WorldAnalyser(terrain_loader=terrain_loader, configuration=terrain_config)
    analysis = analyser.prepare()
    area     = analysis.best_area
    logger.info("  Best area: %s", area)

    # Snapshot the heightmap BEFORE fill so we can see what changed
    before = analysis.heightmap_ground.copy()
    logger.info(
        "  Before fill — min=%d  max=%d  median=%.1f",
        int(before.min()), int(before.max()), float(np.median(before)),
    )

    # --- Phase 1: Fill depressions ---
    logger.info("[Phase 1] Running fill_depressions (threshold=8)...")
    fill_depressions(editor=editor, analysis=analysis, depression_threshold=8)

    after_fill = analysis.heightmap_ground.copy()
    logger.info(
        "  After fill (in-memory, pre-refresh) — min=%d  max=%d  median=%.1f",
        int(after_fill.min()), int(after_fill.max()), float(np.median(after_fill)),
    )

    changed_mask = after_fill != before
    logger.info(
        "  Cells changed by fill_depressions: %d / %d",
        int(changed_mask.sum()), before.size,
    )

    # --- Flush blocks to Minecraft ---
    logger.info("[Phase 2] Flushing blocks...")
    editor.flushBuffer()
    logger.info("  ✓ Flush done.")

    # Re-fetch using the HTTP API with MOTION_BLOCKING_NO_PLANTS — same type
    # as world analysis — to get the authoritative ground Y after terraforming.
    logger.info("[Phase 2b] Refreshing heightmap_ground via HTTP API...")
    refresh_ground_heightmap(terrain_loader, analysis)
    logger.info(
        "  After refresh (in-memory) — min=%d  max=%d  median=%.1f",
        int(analysis.heightmap_ground.min()),
        int(analysis.heightmap_ground.max()),
        float(np.median(analysis.heightmap_ground)),
    )

    # --- Phase 3: Re-fetch heightmap from Minecraft to verify ---
    logger.info("[Phase 3] Re-fetching MOTION_BLOCKING_NO_PLANTS from Minecraft to verify...")
    # HTTP API returns first-air Y (surface+1), same convention as
    # analysis.heightmap_ground — no adjustment needed.
    fetched_raw = np.asarray(
        terrain_loader.get_heightmap(
            area.x_from, area.z_from,
            area.width,  area.depth,
            "MOTION_BLOCKING_NO_PLANTS",
        ),
        dtype=np.float32,
    )
    logger.info(
        "  Fetched (first-air Y) — min=%d  max=%d  median=%.1f",
        int(fetched_raw.min()), int(fetched_raw.max()), float(np.median(fetched_raw)),
    )

    # after refresh, analysis.heightmap_ground is the authoritative map
    after_inmem = analysis.heightmap_ground.copy()

    # --- Phase 4: Compare ---
    logger.info("[Phase 4] Comparing in-memory (post-refresh) vs fetched...")

    diff = after_inmem.astype(np.float32) - fetched_raw
    abs_diff = np.abs(diff)
    mismatch_mask = abs_diff > 0

    n_mismatch  = int(mismatch_mask.sum())
    total_cells = after_inmem.size

    logger.info("  Cells mismatched : %d / %d  (%.1f%%)",
                n_mismatch, total_cells, 100 * n_mismatch / total_cells)

    if n_mismatch == 0:
        logger.info("  ✓ Perfect match — in-memory heightmap is correct.")
        return 0

    logger.info("  Max abs diff     : %d", int(abs_diff.max()))
    logger.info("  Mean abs diff    : %.2f", float(abs_diff[mismatch_mask].mean()))
    logger.info("  Median abs diff  : %.2f", float(np.median(abs_diff[mismatch_mask])))

    # Direction bias
    over  = int((diff[mismatch_mask] > 0).sum())
    under = int((diff[mismatch_mask] < 0).sum())
    logger.info(
        "  In-memory HIGHER than fetched: %d cells   LOWER: %d cells",
        over, under,
    )
    if over > under * 2:
        logger.warning("  → In-memory map is consistently OVER-filled (too high).")
    elif under > over * 2:
        logger.warning("  → In-memory map is consistently UNDER-filled (not updated enough).")
    else:
        logger.info("  → Mixed direction — likely floating-point or rounding differences.")

    # Top-10 worst mismatches
    flat_idx  = np.argsort(abs_diff.ravel())[::-1][:10]
    li_arr, lj_arr = np.unravel_index(flat_idx, after_inmem.shape)
    logger.info("  Top-10 worst mismatches (world x, z, in-memory Y, fetched Y, diff):")
    for li, lj in zip(li_arr, lj_arr):
        wx = area.x_from + li
        wz = area.z_from + lj
        ym = int(after_inmem[li, lj])
        yf = int(fetched_raw[li, lj])
        logger.info("    (%d, %d)  in-mem=%d  fetched=%d  diff=%+d", wx, wz, ym, yf, ym - yf)

    # --- Phase 5: Visualise ---
    vmin = int(min(before.min(), fetched_raw.min()))
    vmax = int(max(before.max(), fetched_raw.max()))

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle("Heightmap comparison — fill_depressions", fontsize=13)

    def _show(ax, data, title, cmap="terrain", vmin=vmin, vmax=vmax):
        im = ax.imshow(data.T, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title)
        plt.colorbar(im, ax=ax)

    _show(axes[0, 0], before,       "Before fill (in-memory)")
    _show(axes[0, 1], after_inmem,  "After fill (in-memory)")
    _show(axes[0, 2], fetched_raw,  "After fill (fetched from MC)")
    _show(axes[1, 0], after_inmem - before,    "Delta: fill changed",     cmap="RdBu", vmin=None, vmax=None)
    _show(axes[1, 1], diff,                    "Delta: in-mem vs fetched", cmap="RdBu", vmin=None, vmax=None)
    _show(axes[1, 2], changed_mask.astype(float), "Cells changed by fill", cmap="Reds", vmin=0, vmax=1)

    plt.tight_layout()
    plt.show()

    return 0


if __name__ == "__main__":
    sys.exit(main())
