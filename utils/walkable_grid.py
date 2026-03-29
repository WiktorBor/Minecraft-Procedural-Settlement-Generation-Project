from __future__ import annotations

from collections import deque

import numpy as np

# 4-directional neighbourhood — module-level to avoid re-creating per call
_NEIGHBOURS: list[tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def build_cost_grid(
    local_water: np.ndarray,
    additional_blocked: np.ndarray | None = None,
) -> np.ndarray:
    """
    Build a movement-cost grid from terrain data for use by A*.

    A water cell is heavily penalised (cost 20). Cells in `additional_blocked`
    (building interiors, steep slopes, etc.) are impassable (cost inf).
    All other cells have a base cost of 1.

    Parameters
    ----------
    local_water : np.ndarray
        2-D array where True (or non-zero) indicates a water cell.
    additional_blocked : np.ndarray or None
        Optional 2-D boolean array of the same shape for any extra impassable
        cells. Combined with water via logical OR at the inf tier.

    Returns
    -------
    np.ndarray
        2-D float array of the same shape as `local_water`.
    """
    costs = np.ones_like(local_water, dtype=float)
    costs[local_water.astype(bool)] = 20.0

    if additional_blocked is not None:
        costs[additional_blocked.astype(bool)] = np.inf

    return costs


def nearest_walkable(
    start_i: int,
    start_j: int,
    walkable: np.ndarray,
    max_radius: int = 5,
) -> tuple[int, int] | None:
    """
    BFS from (start_i, start_j) to the nearest walkable cell.

    Parameters
    ----------
    start_i, start_j : int
        Starting grid coordinates.
    walkable : np.ndarray
        2-D boolean array (True = walkable).
    max_radius : int
        Maximum BFS distance to search (default 5).

    Returns
    -------
    (i, j) of the nearest walkable cell, or None if none found within radius.
    """
    if walkable[start_i, start_j]:
        return (start_i, start_j)

    w, d = walkable.shape
    seen = np.zeros((w, d), dtype=bool)
    seen[start_i, start_j] = True

    queue: deque[tuple[int, int, int]] = deque([(start_i, start_j, 0)])

    while queue:
        li, lj, dist = queue.popleft()
        if dist >= max_radius:
            continue
        for di, dj in _NEIGHBOURS:
            ni, nj = li + di, lj + dj
            if 0 <= ni < w and 0 <= nj < d and not seen[ni, nj]:
                seen[ni, nj] = True
                if walkable[ni, nj]:
                    return (ni, nj)
                queue.append((ni, nj, dist + 1))

    return None