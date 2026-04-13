from __future__ import annotations
import random
import numpy as np
from .geometry import HasBounds

def expand_path_to_width(
    path_cells: set[tuple[int, int]],
    path_width: int,
    bounds: HasBounds, # Accepts BuildArea, Plot, or any RectangularArea
    blocked: np.ndarray | set[tuple[int, int]],
    organic: bool = True,
    seed: int = 42,
) -> set[tuple[int, int]]:
    """
    Expand centre-line path to a wider footprint using unified bounds protocol.
    """
    if path_width <= 1:
        return path_cells

    # Access Protocol attributes directly
    x_min, x_max = int(bounds.x_from), int(bounds.x_to)
    z_min, z_max = int(bounds.z_from), int(bounds.z_to)
    
    radius = path_width / 2
    r_sq = radius * radius
    rng = random.Random(seed)
    expanded: set[tuple[int, int]] = set()

    for bx, bz in path_cells:
        r_int = int(radius + 1)
        for dx in range(-r_int, r_int + 1):
            for dz in range(-r_int, r_int + 1):
                dist_sq = dx*dx + dz*dz
                if dist_sq > r_sq: continue
                
                # Organic mode creates a less 'perfect' circle for natural paths
                if organic and dist_sq > (r_sq * 0.4) and rng.random() < 0.4:
                    continue

                nx, nz = bx + dx, bz + dz
                if not (x_min <= nx <= x_max and z_min <= nz <= z_max):
                    continue

                # Handle either numpy occupancy masks or coordinate sets
                if isinstance(blocked, np.ndarray):
                    # Check local index relative to bounds
                    if blocked[nx - x_min, nz - z_min]: continue
                elif (nx, nz) in blocked:
                    continue
                    
                expanded.add((nx, nz))

    return expanded