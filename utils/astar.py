"""
A* pathfinding on a 2D grid with height step constraint.
Paths only move between cells where the height difference is at most
`height_step_max` blocks.
"""
from __future__ import annotations

import heapq

import numpy as np

# 4-directional neighbourhood offsets (dx, dz).
# Extend to 8 directions here if diagonal movement is ever needed.
_NEIGHBOURS: list[tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def find_path(
    walkable_2d: np.ndarray,
    heightmap: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    height_step_max: int = 2,
    height_cost: float = 0.2,
    costs: np.ndarray | None = None,
) -> list[tuple[int, int]] | None:
    """
    Find a path from start to goal using A* on a 2D grid.

    Parameters
    ----------
    walkable_2d : np.ndarray
        Boolean 2D array (True = can walk). Shape (width, depth).
    heightmap : np.ndarray
        2D array of ground height, same shape as walkable_2d.
    start : (local_x, local_z)
        Start cell indices.
    goal : (local_x, local_z)
        Goal cell indices.
    height_step_max : int
        Maximum allowed height difference between adjacent cells (default 2).
    height_cost : float
        Extra cost per block of height difference (default 0.2).
    costs : np.ndarray or None
        Optional per-cell movement cost array, same shape as walkable_2d.
        If None, all walkable cells cost 1.0.

    Returns
    -------
    list of (local_x, local_z) from start to goal inclusive, or None if no
    path exists.
    """
    if walkable_2d.shape != heightmap.shape:
        raise ValueError("walkable_2d and heightmap must have the same shape")

    h_w, h_d = walkable_2d.shape
    goal_x, goal_z = goal
    start_x, start_z = start

    # Bounds and walkability guards
    if not (0 <= start_x < h_w and 0 <= start_z < h_d):
        return None
    if not (0 <= goal_x < h_w and 0 <= goal_z < h_d):
        return None
    if not walkable_2d[start_x, start_z]:
        return None
    if not walkable_2d[goal_x, goal_z]:
        return None

    # Array-backed state — much faster than dicts / sets on large grids.
    # g_score[x, z] = best known cost to reach (x, z); inf = unvisited.
    g_score = np.full((h_w, h_d), np.inf, dtype=np.float32)
    g_score[start_x, start_z] = 0.0

    # came_from[x, z] = (px, pz) of the predecessor; (-1, -1) = no predecessor
    came_from = np.full((h_w, h_d, 2), -1, dtype=np.int32)

    # closed[x, z] = True once a cell is finalised
    closed = np.zeros((h_w, h_d), dtype=bool)

    heights: np.ndarray = heightmap.astype(np.float32, copy=False)

    # Open set: (f_score, tie-break counter, x, z)
    counter = 0
    h_start = abs(start_x - goal_x) + abs(start_z - goal_z)
    open_set: list[tuple[float, int, int, int]] = [
        (float(h_start), 0, start_x, start_z)
    ]

    while open_set:
        _, _, ix, iz = heapq.heappop(open_set)

        if closed[ix, iz]:
            continue
        closed[ix, iz] = True

        if ix == goal_x and iz == goal_z:
            return _reconstruct_path(came_from, start_x, start_z, goal_x, goal_z)

        my_height: float = heights[ix, iz]
        my_g: float = g_score[ix, iz]

        for dx, dz in _NEIGHBOURS:
            nx, nz = ix + dx, iz + dz

            if not (0 <= nx < h_w and 0 <= nz < h_d):
                continue
            if not walkable_2d[nx, nz]:
                continue

            height_diff: float = abs(my_height - heights[nx, nz])
            if height_diff > height_step_max:
                continue

            cell_cost = float(costs[nx, nz]) if costs is not None else 1.0
            movement_penalty = cell_cost if cell_cost != np.inf else 999999
            tentative_g = my_g + movement_penalty + (height_cost * height_diff)
            
            if tentative_g < g_score[nx, nz]:
                g_score[nx, nz] = tentative_g
                came_from[nx, nz, 0] = ix
                came_from[nx, nz, 1] = iz
                counter += 1
                f: float = tentative_g + abs(nx - goal_x) + abs(nz - goal_z)
                heapq.heappush(open_set, (f, counter, nx, nz))

    return None


def _reconstruct_path(
    came_from: np.ndarray,
    start_x: int,
    start_z: int,
    goal_x: int,
    goal_z: int,
) -> list[tuple[int, int]]:
    """Walk came_from backwards from goal to start and return the reversed path."""
    path: list[tuple[int, int]] = []
    cx, cz = goal_x, goal_z
    while not (cx == start_x and cz == start_z):
        path.append((cx, cz))
        cx, cz = int(came_from[cx, cz, 0]), int(came_from[cx, cz, 1])
    path.append((start_x, start_z))
    path.reverse()
    return path