"""
debug/test_fill_depression.py
------------------------------
Runs fill_depressions, flushes, then verifies the in-memory heightmap
matches the freshly fetched ground heightmap from Minecraft.

Run with:  python -m debug.test_fill_depression
"""
from __future__ import annotations

import logging
import sys

import numpy as np
from gdpc import Editor

from analysis.world_analysis import WorldAnalyser
from data.configurations import TerrainConfig
from utils.http_client import GDMCClient
from world_interface.terrain_loader import TerrainLoader
from world_interface.terraforming import fill_depressions, recompute_all_maps

logging.basicConfig(
    level=logging.DEBUG,
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

    # --- Analyse ---
    logger.info("Analysing world...")
    analyser = WorldAnalyser(terrain_loader=terrain_loader, configuration=terrain_config)
    analysis = analyser.prepare()
    area     = analysis.best_area
    logger.info("  Best area: %s", area)

    before = analysis.heightmap_ground.copy()
    logger.info(
        "  Before — min=%d  max=%d  median=%.1f",
        int(before.min()), int(before.max()), float(np.median(before)),
    )

    # --- Terraforming ---
    logger.info("Running fill_depressions (auto threshold)...")
    fill_depressions(editor=editor, analysis=analysis, config=terrain_config)

    after_fill = analysis.heightmap_ground.copy()
    changed    = int((after_fill != before).sum())
    logger.info(
        "  After fill (in-memory) — min=%d  max=%d  median=%.1f  changed=%d cells",
        int(after_fill.min()), int(after_fill.max()), float(np.median(after_fill)), changed,
    )

    # --- Flush ---
    logger.info("Flushing to Minecraft...")
    editor.flushBuffer()

    # --- Refresh heightmap from HTTP API ---
    logger.info("Refreshing heightmap_ground via HTTP API (MOTION_BLOCKING_NO_PLANTS)...")
    recompute_all_maps(editor, analysis, terrain_config, terrain_loader=terrain_loader)
    after_refresh = analysis.heightmap_ground.copy()
    logger.info(
        "  After refresh — min=%d  max=%d  median=%.1f",
        int(after_refresh.min()), int(after_refresh.max()), float(np.median(after_refresh)),
    )

    # --- Verify ---
    logger.info("Verifying in-memory vs fetched...")
    diff         = after_fill.astype(np.float32) - after_refresh.astype(np.float32)
    abs_diff     = np.abs(diff)
    n_mismatch   = int((abs_diff > 0).sum())

    logger.info(
        "  Mismatched cells: %d / %d  (%.1f%%)",
        n_mismatch, after_fill.size, 100 * n_mismatch / after_fill.size,
    )

    if n_mismatch == 0:
        logger.info("  ✓ Perfect match — heightmap_ground is correct.")
    else:
        logger.info("  Max abs diff : %d", int(abs_diff.max()))
        logger.info("  Mean abs diff: %.2f", float(abs_diff[abs_diff > 0].mean()))

        over  = int((diff[diff != 0] > 0).sum())
        under = int((diff[diff != 0] < 0).sum())
        logger.info("  In-memory HIGHER: %d  LOWER: %d", over, under)

        # Top-5 worst
        flat_idx       = np.argsort(abs_diff.ravel())[::-1][:5]
        li_arr, lj_arr = np.unravel_index(flat_idx, after_fill.shape)
        logger.info("  Top-5 mismatches (x, z, in-mem, fetched, diff):")
        for li, lj in zip(li_arr, lj_arr):
            if abs_diff[li, lj] == 0:
                break
            logger.info(
                "    (%d, %d)  in-mem=%d  fetched=%d  diff=%+d",
                area.x_from + li, area.z_from + lj,
                int(after_fill[li, lj]), int(after_refresh[li, lj]),
                int(diff[li, lj]),
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
