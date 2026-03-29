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
    Terrain-weighted Poisson disk sampling (Bridson's algorithm).

    Parameters
    ----------
    width, height : int
        Size of the rectangular area.
    radius : float
        Minimum distance between samples.
    score_map : np.ndarray or None
        Terrain preference map [x, z] with values 0..1 (1 = preferable).
        Must have shape (width, depth) or broadcastable equivalent.
    seed : int or None
        Random seed for reproducibility.
    k : int
        Number of candidate attempts per active point (default 30).

    Returns
    -------
    np.ndarray
        Shape (N, 2) array of sample coordinates (float32) in local index
        space [0, width) × [0, height).
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    cell_size = radius / math.sqrt(2)
    grid_w = int(width / cell_size) + 1
    grid_d = int(depth / cell_size) + 1
    radius_sq = radius * radius  # hoisted — used in every neighbour check

    # numpy grid: stores sample index + 1 at each cell (0 = empty).
    # Using indices avoids storing float tuples and makes lookups cheaper.
    grid = np.zeros((grid_w, grid_d), dtype=np.int32)

    samples: list[tuple[float, float]] = []
    active: list[tuple[float, float]] = []

    # Pre-flatten score_map to float32 once so per-point lookup is just indexing.
    if score_map is not None:
        _score: np.ndarray = np.asarray(score_map, dtype=np.float32)
    else:
        _score = None

    def _terrain_score(x: float, z: float) -> float:
        if _score is None:
            return 1.0
        return float(_score[min(int(x), _score.shape[0] - 1),
                             min(int(z), _score.shape[1] - 1)])

    def _add_sample(x: float, z: float) -> None:
        idx = len(samples) + 1          # 1-based so 0 stays "empty"
        samples.append((x, z))
        active.append((x, z))
        grid[int(x / cell_size), int(z / cell_size)] = idx

    def _is_valid(x: float, z: float) -> bool:
        gx = int(x / cell_size)
        gz = int(z / cell_size)
        x0, x1 = max(gx - 2, 0), min(gx + 3, grid_w)
        z0, z1 = max(gz - 2, 0), min(gz + 3, grid_d)

        window = grid[x0:x1, z0:z1]          # numpy slice — no Python loop
        occupied = window[window > 0] - 1     # convert to 0-based sample indices

        if occupied.size == 0:
            return True

        nbrs = np.array(samples, dtype=np.float32)[occupied]  # (m, 2)
        dx = nbrs[:, 0] - x
        dz = nbrs[:, 1] - z
        return bool(np.all(dx * dx + dz * dz >= radius_sq))

    # ------------------------------------------------------------------
    # First point — rejection-sampled against terrain score
    # ------------------------------------------------------------------
    while True:
        x = random.uniform(0, width)
        z = random.uniform(0, depth)
        if random.random() < _terrain_score(x, z):
            break
    _add_sample(x, z)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    while active:
        idx = random.randrange(len(active))
        px, pz = active[idx]
        found = False

        # Batch-generate all k candidates at once — one numpy call instead of k
        angles = np.random.uniform(0, 2 * math.pi, k)
        dists  = np.random.uniform(radius, 2 * radius, k)
        cands_x = px + np.cos(angles) * dists
        cands_z = pz + np.sin(angles) * dists

        for cx, cz in zip(cands_x, cands_z):
            if not (0 <= cx < width and 0 <= cz < depth):
                continue
            if random.random() >= _terrain_score(cx, cz):
                continue
            if _is_valid(cx, cz):
                _add_sample(cx, cz)
                found = True
                break

        if not found:
            # O(1) swap-and-pop instead of O(n) mid-list removal
            active[idx] = active[-1]
            active.pop()

    return np.array(samples, dtype=np.float32)