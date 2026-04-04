from __future__ import annotations

import random

import numpy as np


def expand_path_to_width(
    path_cells: set[tuple[int, int]],
    path_width: int,
    bounds: tuple[int, int, int, int],
    blocked: np.ndarray | set[tuple[int, int]],
    organic: bool = True,
    seed: int = 42,
) -> set[tuple[int, int]]:
    """
    Expand centre-line ``path_cells`` to a wider footprint.

    When ``organic`` is True (default) the edges are randomised so the path
    looks hand-laid rather than machine-stamped.  Edge cells have a ~40%
    chance of being omitted, producing an irregular silhouette that suits
    a village aesthetic.

    Parameters
    ----------
    path_cells : set of (x, z)
        Centre-line cells of the path.
    path_width : int
        Desired total width.  Expansion radius = width // 2.
    bounds : (x_min, x_max, z_min, z_max)
        Inclusive bounds for expanded cells.
    blocked : np.ndarray or set of (x, z)
        True = blocked.  Numpy path preferred for performance.
    organic : bool
        If True, randomly drop edge cells for a natural look.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    set of (x, z)
        Expanded cell coordinates.
    """
    if path_width <= 1:
        return path_cells

    x_min, x_max, z_min, z_max = bounds
    radius = path_width // 2
    r_int = int(radius + 0.5)
    r_sq  = radius * radius

    rng = random.Random(seed)
    expanded: set[tuple[int, int]] = set()

    for bx, bz in path_cells:
        for dx in range(-r_int, r_int + 1):
            for dz in range(-r_int, r_int + 1):
                dist_sq = dx * dx + dz * dz
                if dist_sq > r_sq:
                    continue

                # Organic mode: cells at the outer ring have a chance to be
                # dropped so edges aren't perfectly circular.
                if organic and dist_sq > (r_sq * 0.4):
                    if rng.random() < 0.40:
                        continue

                nx, nz = bx + dx, bz + dz
                if not (x_min <= nx <= x_max and z_min <= nz <= z_max):
                    continue

                if isinstance(blocked, np.ndarray):
                    if blocked[nx - x_min, nz - z_min]:
                        continue
                elif (nx, nz) in blocked:
                    continue

                expanded.add((nx, nz))

    return expanded
