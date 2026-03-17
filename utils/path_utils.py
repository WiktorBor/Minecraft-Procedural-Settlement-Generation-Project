from __future__ import annotations

import numpy as np
from collections import deque

# 4-directional neighbourhood — module-level to avoid re-creating per call
_NEIGHBOURS: list[tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def expand_path_to_width(
    path_cells: set[tuple[int, int]],
    path_width: int,
    bounds: tuple[int, int, int, int],
    blocked: np.ndarray | set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """
    Expands path cells to a square footprint of `path_width` while avoiding
    blocked cells and staying within bounds.

    Args:
        path_cells: Set of (x, z) centre-line cells.
        path_width: Total width in cells (expansion radius = width // 2).
        bounds: (x_min, x_max, z_min, z_max) inclusive bounds.
        blocked: Either a 2-D boolean numpy array (True = blocked) or a set of
                 (x, z) tuples.  Numpy array is preferred for performance.

    Returns:
        Expanded set of (x, z) cells.
    """
    if path_width <= 1:
        return path_cells

    x_min, x_max, z_min, z_max = bounds
    radius = path_width // 2

    # Build offset grid once: shape (side, side, 2)
    side = 2 * radius + 1
    offsets = np.array(
        [(dx, dz) for dx in range(-radius, radius + 1)
                  for dz in range(-radius, radius + 1)],
        dtype=np.int32,
    )  # shape (side², 2)

    # Broadcast all path cells against all offsets in one shot
    centres = np.array(list(path_cells), dtype=np.int32)   # (P, 2)
    candidates = (centres[:, None, :] + offsets[None, :, :]).reshape(-1, 2)
    # candidates shape: (P * side², 2)

    # Bounds filter
    in_bounds = (
        (candidates[:, 0] >= x_min) & (candidates[:, 0] <= x_max) &
        (candidates[:, 1] >= z_min) & (candidates[:, 1] <= z_max)
    )
    candidates = candidates[in_bounds]

    # Blocked filter
    if isinstance(blocked, np.ndarray):
        # Clip to array shape to avoid index errors at the boundary
        cx = np.clip(candidates[:, 0], 0, blocked.shape[0] - 1)
        cz = np.clip(candidates[:, 1], 0, blocked.shape[1] - 1)
        not_blocked = ~blocked[cx, cz]
        candidates = candidates[not_blocked]
    else:
        # Fallback: blocked is a set of tuples
        candidates = candidates[
            [( int(c[0]), int(c[1]) ) not in blocked for c in candidates]
        ]

    return {(int(c[0]), int(c[1])) for c in candidates}


def _nearest_walkable(
    start_li: int,
    start_lj: int,
    walkable: np.ndarray,
    max_radius: int = 5,
) -> tuple[int, int] | None:
    """
    BFS from (start_li, start_lj) to the nearest walkable cell.

    Args:
        start_li, start_lj: Starting grid coordinates.
        walkable: 2-D boolean array (True = walkable).
        max_radius: Maximum BFS distance to search (default 5).

    Returns:
        (li, lj) of nearest walkable cell, or None if none found within radius.
    """
    if walkable[start_li, start_lj]:
        return (start_li, start_lj)

    w, d = walkable.shape
    seen = np.zeros((w, d), dtype=bool)
    seen[start_li, start_lj] = True

    queue: deque[tuple[int, int, int]] = deque([(start_li, start_lj, 0)])

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