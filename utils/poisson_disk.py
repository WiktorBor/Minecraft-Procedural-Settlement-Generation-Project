from __future__ import annotations
import math
import random
import numpy as np

def poisson_disk(
    width: int,
    depth: int,
    radius: float,
    score_map: np.ndarray | None = None,
    seed: int | None = None,
    k: int = 30,
) -> np.ndarray:
    """
    Performance-optimized Poisson disk sampling (Bridson's algorithm).
    Uses a pre-allocated numpy array to prevent O(N^2) overhead.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    cell_size = radius / math.sqrt(2)
    grid_w, grid_d = int(width / cell_size) + 1, int(depth / cell_size) + 1
    radius_sq = radius * radius

    # Pre-allocate memory for performance: (Area / circle area) * safety buffer
    max_estimated = int((width * depth) / (math.pi * (radius**2 / 4))) + 200
    samples_np = np.zeros((max_estimated, 2), dtype=np.float32)
    grid = np.zeros((grid_w, grid_d), dtype=np.int32) # stores index + 1
    
    samples_list: list[tuple[float, float]] = []
    active: list[tuple[float, float]] = []
    sample_count = 0

    def _terrain_score(x: float, z: float) -> float:
        if score_map is None: return 1.0
        ix, iz = int(x), int(z)
        return float(score_map[ix, iz]) if (0 <= ix < width and 0 <= iz < depth) else 0.0

    def _add_sample(x: float, z: float):
        nonlocal sample_count
        samples_np[sample_count] = [x, z]
        samples_list.append((x, z))
        active.append((x, z))
        grid[int(x / cell_size), int(z / cell_size)] = sample_count + 1
        sample_count += 1

    def _is_valid(x: float, z: float) -> bool:
        gx, gz = int(x / cell_size), int(z / cell_size)
        # Check 5x5 neighborhood in grid using a slice
        subset = grid[max(gx-2, 0):min(gx+3, grid_w), max(gz-2, 0):min(gz+3, grid_d)]
        occupied = subset[subset > 0] - 1
        if len(occupied) == 0: return True
        
        # Vectorized distance check against only the relevant neighbors
        nbrs = samples_np[occupied]
        dx, dz = nbrs[:, 0] - x, nbrs[:, 1] - z
        return bool(np.all(dx * dx + dz * dz >= radius_sq))

    # Initial seed point
    found_seed = False
    for _ in range(100):
        sx, sz = random.uniform(0, width), random.uniform(0, depth)
        if random.random() < _terrain_score(sx, sz):
            _add_sample(sx, sz)
            found_seed = True
            break
    if not found_seed: _add_sample(width / 2, depth / 2)

    while active:
        idx = random.randrange(len(active))
        px, pz = active[idx]
        found = False
        
        # Batch generate candidates
        angles = np.random.uniform(0, 2 * math.pi, k)
        dists = np.random.uniform(radius, 2 * radius, k)
        
        for cx, cz in zip(px + np.cos(angles) * dists, pz + np.sin(angles) * dists):
            if 0 <= cx < width and 0 <= cz < depth and \
               random.random() < _terrain_score(cx, cz) and _is_valid(cx, cz):
                _add_sample(cx, cz)
                found = True
                break
        if not found:
            # Swap-and-pop is O(1) compared to O(N) list removal
            active[idx] = active[-1]
            active.pop()

    return np.array(samples_list, dtype=np.float32)