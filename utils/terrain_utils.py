from __future__ import annotations

import numpy as np

from data.build_area import BuildArea
from data.settlement_entities import RectangularArea


def get_area_slice(
    build_area: BuildArea,
    area: RectangularArea,
    terrain: np.ndarray,
) -> np.ndarray:
    """
    Extract a 2-D slice from a map array corresponding to the given area.

    Parameters
    ----------
    build_area : BuildArea
        The active build area, used to convert world coordinates to array indices.
    area : RectangularArea
        The region of interest (world coordinates).
    terrain : np.ndarray
        2-D array to slice (e.g. heightmap, walkable grid).

    Returns
    -------
    np.ndarray
        A 2-D view (or copy if clamped) of `terrain` covering the area,
        clamped to the array bounds.
    """
    ix_start, iz_start = build_area.world_to_index(area.x_from, area.z_from)

    ix_start = max(0, ix_start)
    iz_start = max(0, iz_start)

    ix_end = min(ix_start + area.width,  terrain.shape[0])
    iz_end = min(iz_start + area.depth, terrain.shape[1])

    return terrain[ix_start:ix_end, iz_start:iz_end]