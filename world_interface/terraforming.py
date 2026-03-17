from __future__ import annotations

import numpy as np
from gdpc.editor import Editor
from data.build_area import BuildArea


def terraform_area_real_time(
    editor: Editor,
    heightmap: np.ndarray,
    best_area: BuildArea,
    parent_area: BuildArea,
    max_height_change: float = 0.5,
    block_type: str = "minecraft:dirt",
) -> None:
    """
    Smooth small height variations within best_area by editing blocks in the world.

    Computes a median target height for the area, clamps per-cell adjustments
    to `max_height_change`, then places fill blocks where the terrain is raised.

    Args:
        editor: GDPC Editor instance (use in buffered mode for performance).
        heightmap: 2-D float32 array of terrain heights indexed to parent_area.
        best_area: The sub-area to terraform (world coordinates).
        parent_area: The parent BuildArea that heightmap is indexed against.
        max_height_change: Maximum height adjustment per cell (blocks).
        block_type: Block ID to use for fill (default: minecraft:dirt).

    Note
    ----
    Call this inside an `editor.pushBuffer()` / `editor.popBuffer()` block to
    batch all placements into a single HTTP request rather than one per cell.
    """
    ix_from, iz_from = parent_area.world_to_index(best_area.x_from, best_area.z_from)
    ix_to,   iz_to   = parent_area.world_to_index(best_area.x_to,   best_area.z_to)

    submap = heightmap[ix_from:ix_to + 1, iz_from:iz_to + 1]

    target_height = int(np.round(np.median(submap)))
    diff          = np.clip(target_height - submap, -max_height_change, max_height_change)
    new_heights   = (submap + diff).astype(np.float32)

    # Write smoothed heights back into the parent heightmap
    heightmap[ix_from:ix_to + 1, iz_from:iz_to + 1] = new_heights

    # Place blocks where the terrain needs to be raised (diff > 0)
    for i in range(new_heights.shape[0]):
        for j in range(new_heights.shape[1]):
            x, z = best_area.index_to_world(i, j)
            y    = int(new_heights[i, j])
            editor.placeBlock((x, y, z), block_type)