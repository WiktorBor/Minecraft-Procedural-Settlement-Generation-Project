"""
A* pathfinding on a 2D grid with height step constraint.
Paths only move between cells where the height difference is at most 1 block.
"""

import heapq
from typing import List, Optional, Tuple

import numpy as np


def find_path(
    walkable_2d: np.ndarray,
    heightmap: np.ndarray,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    height_step_max: int = 1,
    height_cost: float = 0.2,
) -> Optional[List[Tuple[int, int]]]:
    """
    Find a path from start to goal using A* on a 2D grid.

    Args:
        walkable_2d: Boolean 2D array (True = can walk). Shape (width, depth).
        heightmap: 2D array of ground height, same shape as walkable_2d.
        start: (local_x, local_z) start cell indices.
        goal: (local_x, local_z) goal cell indices.
        height_step_max: Maximum allowed height difference between adjacent cells (default 1).
        height_cost: Extra cost per block of height difference (default 0.2).

    Returns:
        List of (local_x, local_z) from start to goal (inclusive), or None if no path exists.
    """
    if not walkable_2d[start[0], start[1]]:
        return None
    if not walkable_2d[goal[0], goal[1]]:
        return None

    h_w, h_d = walkable_2d.shape
    if not (0 <= start[0] < h_w and 0 <= start[1] < h_d):
        return None
    if not (0 <= goal[0] < h_w and 0 <= goal[1] < h_d):
        return None

    # 4-neighborhood: (dx, dz)
    neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    def heuristic(ix: int, iz: int) -> float:
        return abs(ix - goal[0]) + abs(iz - goal[1])

    # Priority queue: (f_score, counter, (ix, iz))
    counter = 0
    open_set = [(heuristic(start[0], start[1]), counter, start)]
    came_from: dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    g_score: dict[Tuple[int, int], float] = {start: 0.0}

    while open_set:
        _, _, (ix, iz) = heapq.heappop(open_set)

        if (ix, iz) == goal:
            path: List[Tuple[int, int]] = []
            current: Optional[Tuple[int, int]] = (ix, iz)
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path

        my_height = float(heightmap[ix, iz])
        my_g = g_score[(ix, iz)]

        for (dx, dz) in neighbors:
            nx, nz = ix + dx, iz + dz
            if not (0 <= nx < h_w and 0 <= nz < h_d):
                continue
            if not walkable_2d[nx, nz]:
                continue

            n_height = float(heightmap[nx, nz])
            height_diff = abs(my_height - n_height)
            if height_diff > height_step_max:
                continue

            step_cost = 1.0 + height_cost * height_diff
            tentative_g = my_g + step_cost

            if (nx, nz) not in g_score or tentative_g < g_score[(nx, nz)]:
                came_from[(nx, nz)] = (ix, iz)
                g_score[(nx, nz)] = tentative_g
                counter += 1
                f = tentative_g + heuristic(nx, nz)
                heapq.heappush(open_set, (f, counter, (nx, nz)))

    return None
