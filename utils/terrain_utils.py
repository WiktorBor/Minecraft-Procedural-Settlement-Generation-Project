from __future__ import annotations
import numpy as np
from data.build_area import BuildArea
from .geometry import HasBounds

def get_area_slice(
    build_area: BuildArea,
    area: HasBounds, # Upgraded to Protocol
    terrain: np.ndarray,
) -> np.ndarray:
    """
    Extracts a 2D slice from a map array. 
    Includes safety clamping to prevent crashes on edge-of-map structures.
    """
    # Use int casting to handle float centroids from planning
    x_from, z_from = int(area.x_from), int(area.z_from)
    
    try:
        ix_start, iz_start = build_area.world_to_index(x_from, z_from)
    except ValueError:
        # Fallback for coords slightly outside (e.g. -1 offset)
        ix_start = x_from - build_area.x_from
        iz_start = z_from - build_area.z_from

    # Clamp to array dimensions
    i_min = max(0, ix_start)
    j_min = max(0, iz_start)
    i_max = min(ix_start + int(area.width), terrain.shape[0])
    j_max = min(iz_start + int(area.depth), terrain.shape[1])

    return terrain[i_min:i_max, j_min:j_max]