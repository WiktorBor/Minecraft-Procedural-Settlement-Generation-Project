import numpy as np

def mst_edges(points):
    """
    Compute a minimal spanning tree (MST) over a list of points using Prim's algorithm.
    
    Args:
        points (List[Tuple[float, float]]): list of (x, z) points
    
    Returns:
        List[Tuple[int, int]]: list of edges (i, j) connecting points
    """
    n = len(points)
    if n <= 1:
        return []

    in_mst = [False] * n
    in_mst[0] = True
    edges = []

    points = np.array(points)

    def dist(i, j):
        return np.linalg.norm(points[i] - points[j])

    for _ in range(n - 1):
        best_d = float("inf")
        best_u, best_v = -1, -1
        for u in range(n):
            if not in_mst[u]:
                continue
            for v in range(n):
                if in_mst[v]:
                    continue
                d = dist(u, v)
                if d < best_d:
                    best_d = d
                    best_u, best_v = u, v
        if best_v >= 0:
            in_mst[best_v] = True
            edges.append((best_u, best_v))
    return edges