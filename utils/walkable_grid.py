from __future__ import annotations
from collections import deque
import numpy as np

def build_cost_grid(
    local_water: np.ndarray,
    additional_blocked: np.ndarray | None = None,
) -> np.ndarray:
    """
    Vectorized cost grid construction.
    Water = 20.0, Blocked = inf, Default = 1.0
    """
    costs = np.ones(local_water.shape, dtype=np.float32)
    costs[local_water > 0] = 20.0
    
    if additional_blocked is not None:
        costs[additional_blocked] = np.inf
        
    return costs

def nearest_walkable(
    start_i: int,
    start_j: int,
    walkable: np.ndarray,
    max_radius: int = 15, # Increased default for better path recovery
) -> tuple[int, int] | None:
    if walkable[start_i, start_j]:
        return (start_i, start_j)

    w, d = walkable.shape
    queue = deque([(start_i, start_j, 0)])
    seen = { (start_i, start_j) }

    while queue:
        li, lj, dist = queue.popleft()
        if dist >= max_radius: continue

        for di, dj in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            ni, nj = li + di, lj + dj
            if 0 <= ni < w and 0 <= nj < d and (ni, nj) not in seen:
                if walkable[ni, nj]:
                    return (ni, nj)
                seen.add((ni, nj))
                queue.append((ni, nj, dist + 1))
    return None