from __future__ import annotations

import numpy as np
from gdpc import Block
from gdpc.editor import Editor
from scipy.ndimage import uniform_filter

from data.analysis_results import WorldAnalysisResult


def terraform_area(
    editor: Editor,
    analysis: WorldAnalysisResult,
    passes: int = 3,
    smooth_radius: int = 3,
    max_change_per_pass: float = 1.0,
    block_type: str = "minecraft:dirt",
) -> None:
    """
    Smooth terrain bumps within best_area using iterative neighbourhood
    averaging, producing natural slopes rather than hard flat cuts.

    Holes and caves are intentionally left untouched — call
    seal_cave_openings() AFTER this function to fill those flat and flush
    with the surrounding ground. Separating the two concerns avoids the
    smoother nudging freshly-filled cells back down.

    Only downward smoothing is applied here (bumps are shaved). Cells
    below the local mean are never raised — that is hole-filling territory
    and belongs to seal_cave_openings.

    Algorithm
    ---------
    Each pass:
      1. Compute the neighbourhood mean via uniform filter.
      2. For cells ABOVE the mean: move them down by up to max_change_per_pass.
      3. For cells BELOW the mean: leave them alone (hole-filling is separate).

    Args:
        editor:              GDPC Editor instance (buffered mode recommended).
        analysis:            WorldAnalysisResult — heightmap_ground updated in-place.
        passes:              Number of smoothing iterations (default 3).
        smooth_radius:       Neighbourhood radius for each pass (default 3).
        max_change_per_pass: Max height reduction per cell per pass (default 1.0).
        block_type:          Unused here (kept for API consistency). Removal of
                             blocks uses minecraft:air.

    Call order in settlement_generator.py Phase 2:
        terraform_area_real_time(...)   # smooth bumps with slopes
        seal_cave_openings(...)         # fill holes flat and flush
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground.astype(np.float32)
    w, d      = heightmap.shape
    size      = 2 * smooth_radius + 1

    for _ in range(passes):
        local_mean = uniform_filter(heightmap, size=size, mode="nearest")

        # Only shave downward — never fill upward here.
        # clip so delta is in [-max_change_per_pass, 0]
        delta     = np.clip(local_mean - heightmap, -max_change_per_pass, 0.0)
        heightmap = heightmap + delta

    new_heights = np.round(heightmap).astype(np.int32)
    old_heights = analysis.heightmap_ground.astype(np.int32)

    for i in range(w):
        for j in range(d):
            original_y = int(old_heights[i, j])
            new_y      = int(new_heights[i, j])

            if new_y >= original_y:
                continue  # no change or rounding kept same height

            x, z = area.index_to_world(i, j)

            # Remove blocks from new_y+1 up to original surface
            for y in range(new_y + 1, original_y + 1):
                editor.placeBlock((x, y, z), Block("minecraft:air"))

    # Update heightmap so seal_cave_openings and plot planner see correct heights
    analysis.heightmap_ground[:, :] = new_heights