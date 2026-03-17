from __future__ import annotations

import numpy as np


def get_area_slices(build_area, area, terrain: np.ndarray) -> np.ndarray:
    """
    Extract a 2-D slice from a map array corresponding to the given area.

    Args:
        build_area: Build area object providing world_to_index().
        area: Area object with x_from, z_from, width, depth attributes.
        terrain: 2-D numpy array to slice (e.g. heightmap, walkable grid).

    Returns:
        A 2-D view (or copy if clamped) of `terrain` covering the area,
        clamped to the array bounds.
    """
    ix_start, iz_start = build_area.world_to_index(area.x_from, area.z_from)

    # Clamp start to valid range
    ix_start = max(0, ix_start)
    iz_start = max(0, iz_start)

    # End indices are exclusive (standard numpy slice convention)
    ix_end = min(ix_start + area.width,  terrain.shape[0])
    iz_end = min(iz_start + area.depth, terrain.shape[1])

    return terrain[ix_start:ix_end, iz_start:iz_end]