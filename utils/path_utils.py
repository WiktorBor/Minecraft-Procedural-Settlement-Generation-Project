from typing import Set, Tuple, Optional
import numpy as np
from collections import deque


def expand_path_to_width(
    path_cells: Set[Tuple[int, int]],
    path_width: int,
    bounds: Tuple[int, int, int, int],
    blocked: Set[Tuple[int, int]],
) -> Set[Tuple[int, int]]:
    """
    Expands path cells to a square width while avoiding blocked cells.

    bounds = (x_min, x_max, z_min, z_max)
    """

    if path_width <= 1:
        return path_cells

    x_min, x_max, z_min, z_max = bounds

    radius = path_width // 2
    expanded = set()

    for li, lj in path_cells:

        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):

                nx = li + dx
                nz = lj + dz

                if (nx, nz) in blocked:
                    continue

                if x_min <= nx <= x_max and z_min <= nz <= z_max:
                    expanded.add((nx, nz))

    return expanded

def _nearest_walkable(
    start_li: int,
    start_lj: int,
    walkable: np.ndarray,
    max_radius: int = 5,
) -> Optional[Tuple[int, int]]:
    """BFS from (start_li, start_lj) to nearest walkable cell. Returns (li, lj) or None."""
    if walkable[start_li, start_lj]:
        return (start_li, start_lj)
    w, d = walkable.shape
    queue: deque[Tuple[int, int, int]] = deque([(start_li, start_lj, 0)])
    seen: Set[Tuple[int, int]] = {(start_li, start_lj)}
    neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    while queue:
        li, lj, dist = queue.popleft()
        if dist >= max_radius:
            continue
        for di, dj in neighbors:
            ni, nj = li + di, lj + dj
            if 0 <= ni < w and 0 <= nj < d and (ni, nj) not in seen:
                seen.add((ni, nj))
                if walkable[ni, nj]:
                    return (ni, nj)
                queue.append((ni, nj, dist + 1))
    return None