from __future__ import annotations

import numpy as np


def mst_edges(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
    """
    Compute a Minimum Spanning Tree (MST) over a list of 2D points using Prim's algorithm.

    Runs in O(n²) time using a maintained min-distance array, which is optimal for
    dense graphs represented as an implicit distance matrix.

    Args:
        points: List of (x, z) coordinates.

    Returns:
        List of (i, j) index pairs representing MST edges.
    """
    n = len(points)
    if n <= 1:
        return []

    pts = np.array(points, dtype=np.float32)  # shape (n, 2)

    in_mst = np.zeros(n, dtype=bool)
    in_mst[0] = True

    # min_dist[v]  = cheapest known distance from v to any node already in the MST
    # nearest[v]   = the MST node that achieves min_dist[v]
    min_dist = np.full(n, np.inf, dtype=np.float32)
    nearest = np.zeros(n, dtype=np.int32)

    # Initialise from node 0
    diffs = pts[1:] - pts[0]                          # (n-1, 2)
    min_dist[1:] = np.sqrt((diffs ** 2).sum(axis=1))  # Euclidean to node 0

    edges: list[tuple[int, int]] = []

    for _ in range(n - 1):
        # Pick the cheapest outside node
        candidates = np.where(~in_mst, min_dist, np.inf)
        v = int(np.argmin(candidates))

        edges.append((int(nearest[v]), v))
        in_mst[v] = True

        # Update min_dist for all remaining outside nodes against newly added v
        outside = ~in_mst
        diffs = pts[outside] - pts[v]                        # (k, 2)
        new_dists = np.sqrt((diffs ** 2).sum(axis=1))        # (k,)

        outside_idx = np.where(outside)[0]
        improved = new_dists < min_dist[outside_idx]
        min_dist[outside_idx[improved]] = new_dists[improved]
        nearest[outside_idx[improved]] = v

    return edges