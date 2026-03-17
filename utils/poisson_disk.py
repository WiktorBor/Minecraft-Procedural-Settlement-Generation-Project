import math
import random
import numpy as np

def poisson_disk(width, height, radius, score_map=None, seed=None, k=30) -> np.ndarray:
    """
    Terrain-weighted Poisson disk sampling.

    Parameters
    ----------
    width, height : int
        Size of the rectangular area
    radius : float
        Minimum distance between samples
    score_map : np.ndarray or None
        Terrain preference map [x,z] with values 0..1 (1 = preferable).
    seed : int or None
        Random seed
    k : int
        Attempts per active point

    Returns
    -------
    np.ndarray
        Nx2 array of sample coordinates (float) in local index space [0, width), [0, height).
    """

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    cell_size = radius / math.sqrt(2)
    grid_w = int(width / cell_size) + 1
    grid_h = int(height / cell_size) + 1

    # grid stores nearest sample per cell (for distance checking)
    grid = [[None for _ in range(grid_h)] for _ in range(grid_w)]

    samples = []
    active = []

    # helper for safe terrain score lookup
    def terrain_score(x, z):
        if score_map is None:
            return 1.0
        ix = min(int(x), score_map.shape[0] - 1)
        iz = min(int(z), score_map.shape[1] - 1)
        return score_map[ix, iz]

    # ------------------
    # first point
    # ------------------
    while True:
        x = random.uniform(0, width)
        z = random.uniform(0, height)
        if random.random() < terrain_score(x, z):
            break

    samples.append((x, z))
    active.append((x, z))

    gx = int(x / cell_size)
    gz = int(z / cell_size)
    grid[gx][gz] = (x, z)

    # ------------------
    # main loop
    # ------------------
    while active:
        idx = random.randrange(len(active))
        px, pz = active[idx]
        found = False

        for _ in range(k):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(radius, 2 * radius)

            x = px + math.cos(angle) * dist
            z = pz + math.sin(angle) * dist

            if not (0 <= x < width and 0 <= z < height):
                continue

            if random.random() >= terrain_score(x, z):
                continue

            gx = int(x / cell_size)
            gz = int(z / cell_size)

            ok = True
            for ix in range(max(gx - 2, 0), min(gx + 3, grid_w)):
                for iz in range(max(gz - 2, 0), min(gz + 3, grid_h)):
                    neighbor = grid[ix][iz]
                    if neighbor is None:
                        continue
                    dx = neighbor[0] - x
                    dz = neighbor[1] - z
                    if dx * dx + dz * dz < radius * radius:
                        ok = False
                        break
                if not ok:
                    break

            if ok:
                samples.append((x, z))
                active.append((x, z))
                grid[gx][gz] = (x, z)
                found = True
                break

        if not found:
            active.pop(idx)

    return np.array(samples, dtype=float)