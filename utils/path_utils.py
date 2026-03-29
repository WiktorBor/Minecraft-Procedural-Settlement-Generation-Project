from __future__ import annotations

import numpy as np

# 4-directional neighbourhood — module-level to avoid re-creating per call
_NEIGHBOURS: list[tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def expand_path_to_width(
    path_cells: set[tuple[int, int]],
    path_width: int,
    bounds: tuple[int, int, int, int],
    blocked: np.ndarray | set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """
    Expand path cells to a square footprint of `path_width` while avoiding
    blocked cells and staying within bounds.

    Parameters
    ----------
    path_cells : set of (x, z)
        Centre-line cells of the path.
    path_width : int
        Total width in cells (expansion radius = width // 2).
    bounds : (x_min, x_max, z_min, z_max)
        Inclusive bounds for the expanded cells.
    blocked : np.ndarray or set of (x, z)
        Either a 2-D boolean array (True = blocked, origin at x_min/z_min) or
        a set of world (x, z) tuples.  The numpy array path is preferred for
        performance on large grids.

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

    expanded: set[tuple[int, int]] = set()

    for bx, bz in path_cells:
        for dx in range(-r_int, r_int + 1):
            for dz in range(-r_int, r_int + 1):
                if (dx ** 2 + dz ** 2) <= radius ** 2:
                    nx, nz = bx + dx, bz + dz
                    if x_min <= nx <= x_max and z_min <= nz <= z_max:
                        if isinstance(blocked, np.ndarray):
                            if not blocked[nx - x_min, nz - z_min]:
                                expanded.add((nx, nz))
                        elif (nx, nz) not in blocked:
                            expanded.add((nx, nz))

    return expanded