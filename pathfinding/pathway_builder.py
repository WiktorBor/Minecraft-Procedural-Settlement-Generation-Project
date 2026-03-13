"""
Pathway builder: builds a walkable grid, computes building front positions,
connects them via MST and A* pathfinding, and places path blocks in the world.
"""

from collections import deque
from typing import List, Optional, Set, Tuple

import numpy as np
from gdpc import Block

from pathfinding.astar import find_path
from utils.block_utils import get_biome_palette
from data.build_area import BuildArea
from data.analysis_results import WorldAnalysisResult


def _is_water_column(world: WorldAnalysisResult, li_global: int, lj_global: int) -> bool:
    """
    Return True if this column contains water using the precomputed water mask.
    """
    return world.water_mask[li_global, lj_global]

def _world_to_best_area_local(wx: int, wz: int, best_area: BuildArea) -> Tuple[int, int]:
    """Convert world (x, z) to local indices (i, j) relative to best_area."""
    return (wx - best_area.x_from, wz - best_area.z_from)


def _local_to_world(li: int, lj: int, best_area: BuildArea) -> Tuple[int, int]:
    """Convert local indices (i, j) to world (x, z)."""
    return (best_area.x_from + li, best_area.z_from + lj)


def _get_heightmap_slice(world: WorldAnalysisResult) -> np.ndarray:
    """Return heightmap_ground sliced to best_area (same grid as settlement local)."""
    build_area = world.build_area
    best_area = world.best_area
    gx = best_area.x_from - build_area.x_from
    gz = best_area.z_from - build_area.z_from
    w, d = best_area.width, best_area.depth
    return world.heightmap_ground[gx : gx + w, gz : gz + d].copy()


def _build_walkable_grid(
    world: WorldAnalysisResult,
    buildings: List[dict],
    buffer_blocks: int = 1,
) -> np.ndarray:
    """
    Build a boolean grid (True = walkable) over best_area.
    Blocked = building footprints + buffer. Same shape as best_area (width x depth).
    """
    best_area = world.best_area
    area_width = best_area.width
    area_depth = best_area.depth
    walkable = np.ones((area_width, area_depth), dtype=bool)

    for b in buildings:
        pos = b["position"]
        size = b["size"]
        x, y, z = pos
        width, _, depth = size
        # Footprint in world: x..x+width-1, z..z+depth-1. Add buffer.
        x_lo = max(best_area.x_from, x - buffer_blocks)
        x_hi = min(best_area.x_to, x + width - 1 + buffer_blocks)
        z_lo = max(best_area.z_from, z - buffer_blocks)
        z_hi = min(best_area.z_to, z + depth - 1 + buffer_blocks)
        for wx in range(x_lo, x_hi + 1):
            for wz in range(z_lo, z_hi + 1):
                li, lj = _world_to_best_area_local(wx, wz, best_area)
                if 0 <= li < area_width and 0 <= lj < area_depth:
                    walkable[li, lj] = False

    return walkable


def _building_footprint_set(
    buildings: List[dict],
    best_area: BuildArea,
) -> Set[Tuple[int, int]]:
    """Set of (world_x, world_z) that lie inside any building footprint (no buffer)."""
    footprint: Set[Tuple[int, int]] = set()
    for b in buildings:
        x, y, z = b["position"]
        width, _, depth = b["size"]
        for wx in range(x, x + width):
            for wz in range(z, z + depth):
                if best_area.x_from <= wx <= best_area.x_to and best_area.z_from <= wz <= best_area.z_to:
                    footprint.add((wx, wz))
    return footprint


def _expand_path_to_width(
    path_cells: Set[Tuple[int, int]],
    path_width: int,
    best_area: BuildArea,
    building_footprints: Set[Tuple[int, int]],
) -> Set[Tuple[int, int]]:
    """
    Expand each path cell to a path_width x path_width area (e.g. 3x3).
    Only add cells that are inside best_area and not inside any building footprint.
    """
    if path_width <= 1:
        return path_cells
    radius = path_width // 2  # 3 -> 1, so ±1 in each direction
    expanded: Set[Tuple[int, int]] = set()
    for (wx, wz) in path_cells:
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                nw = (wx + dx, wz + dz)
                if nw in building_footprints:
                    continue
                if best_area.x_from <= nw[0] <= best_area.x_to and best_area.z_from <= nw[1] <= best_area.z_to:
                    expanded.add(nw)
    return expanded


def _nearest_walkable(
    start_li: int,
    start_lj: int,
    walkable: np.ndarray,
    max_radius: int = 5,
) -> Optional[Tuple[int, int]]:
    """BFS from (start_li, start_lj) to nearest walkable cell. Returns (li, lj) or None."""
    if walkable[start_li, start_lj]:
        return (start_li, start_lj)
    w, d = walkable.shape
    queue: deque[Tuple[int, int, int]] = deque([(start_li, start_lj, 0)])
    seen: Set[Tuple[int, int]] = {(start_li, start_lj)}
    neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    while queue:
        li, lj, dist = queue.popleft()
        if dist >= max_radius:
            continue
        for (di, dj) in neighbors:
            ni, nj = li + di, lj + dj
            if 0 <= ni < w and 0 <= nj < d and (ni, nj) not in seen:
                seen.add((ni, nj))
                if walkable[ni, nj]:
                    return (ni, nj)
                queue.append((ni, nj, dist + 1))
    return None


def _front_position(building: dict, best_area: BuildArea) -> Tuple[int, int]:
    """
    Return world (x, z) of the door-front cell (one block in front of the door).
    Front = wall at min Z, door at (x + width//2, z); so front cell = (x + width//2, z - 1).
    """
    x, y, z = building["position"]
    width, _, depth = building["size"]
    fx = x + width // 2
    fz = z - 1
    return (fx, fz)


def _mst_edges(fronts_world: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Minimum spanning tree (Prim) over building indices. Returns list of edges (i, j).
    Edge weight = Euclidean distance between front positions.
    """
    n = len(fronts_world)
    if n <= 1:
        return []

    def dist(i: int, j: int) -> float:
        a, b = fronts_world[i], fronts_world[j]
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    in_mst = [False] * n
    in_mst[0] = True
    edges: List[Tuple[int, int]] = []
    for _ in range(n - 1):
        best_dist = float("inf")
        best_u, best_v = -1, -1
        for u in range(n):
            if not in_mst[u]:
                continue
            for v in range(n):
                if in_mst[v]:
                    continue
                d = dist(u, v)
                if d < best_dist:
                    best_dist = d
                    best_u, best_v = u, v
        if best_u < 0:
            break
        in_mst[best_v] = True
        edges.append((best_u, best_v))
    return edges


def _path_blocks_from_biome(world: WorldAnalysisResult) -> str:
    """Sample biome at center of best_area and return path block id."""
    best_area = world.best_area
    cx = best_area.x_from + best_area.width // 2
    cz = best_area.z_from + best_area.depth // 2
    build_area = world.build_area
    bi = cx - build_area.x_from
    bj = cz - build_area.z_from
    if 0 <= bi < world.biomes.shape[0] and 0 <= bj < world.biomes.shape[1]:
        biome_id = str(world.biomes[bi, bj])
        if "desert" in biome_id:
            return get_biome_palette("desert")["path"]
        if "taiga" in biome_id or "snow" in biome_id:
            return get_biome_palette("taiga")["path"]
        if "savanna" in biome_id or "badlands" in biome_id:
            return get_biome_palette("mountain")["path"]
    return get_biome_palette("plains")["path"]


def build_pathways(
    world: WorldAnalysisResult,
    buildings: List[dict],
    editor,
    path_block: Optional[str] = None,
    buffer_blocks: int = 1,
    path_width: int = 3,
    path_y_below: int = 1,
) -> None:
    """
    Build pathways with a clear start and stop like village paths.

    Start = one corner of the site (min X, min Z). Stop = opposite corner (max X, max Z).
    Paths are 3x3, begin at start, connect to the front of every house (via MST),
    and end at stop. Path blocks are placed path_y_below blocks under the surface.

    Args:
        world: WorldAnalysisResult with build_area, best_area, heightmap_ground, biomes.
        buildings: List of building dicts with 'position' (x,y,z) and 'size' (w,h,d).
        editor: GDMC Editor for block placement.
        path_block: Block id for path. If None, chosen from biome.
        buffer_blocks: Extra cells to mark blocked around each building (default 1).
        path_width: Width of path in blocks (e.g. 3 for 3x3). Default 3.
        path_y_below: Place path this many blocks below surface (default 1).
    """
    if not buildings:
        return

    best_area = world.best_area
    build_area = world.build_area
    area_width = best_area.width
    area_depth = best_area.depth

    walkable = _build_walkable_grid(world, buildings, buffer_blocks=buffer_blocks)
    heightmap_local = _get_heightmap_slice(world)

    if path_block is None:
        path_block = _path_blocks_from_biome(world)

    # Front positions in world and local; snap to walkable if needed
    fronts_world: List[Tuple[int, int]] = []
    fronts_local: List[Tuple[int, int]] = []

    for b in buildings:
        fw = _front_position(b, best_area)
        li, lj = _world_to_best_area_local(fw[0], fw[1], best_area)
        if 0 <= li < area_width and 0 <= lj < area_depth:
            snapped = _nearest_walkable(li, lj, walkable)
            if snapped is not None:
                fronts_local.append(snapped)
                fronts_world.append(_local_to_world(snapped[0], snapped[1], best_area))
            else:
                fronts_local.append((li, lj))
                fronts_world.append(fw)
        else:
            fronts_world.append(fw)
            fronts_local.append((li, lj))

    path_cells: Set[Tuple[int, int]] = set()

    # Choose start/stop along a line perpendicular to house fronts.
    # Fronts face -Z, so we run the main path roughly along X at the front Z level.
    if fronts_world:
        front_z = fronts_world[0][1]
        min_front_x = min(fx for fx, _ in fronts_world)
        max_front_x = max(fx for fx, _ in fronts_world)
        # Start a bit before the first house and stop a bit after the last.
        start_world = (
            max(best_area.x_from, min_front_x - 6),
            front_z,
        )
        stop_world = (
            min(best_area.x_to, max_front_x + 6),
            front_z,
        )
    else:
        # Fallback to full-span corners if for some reason we have no fronts.
        start_world = (best_area.x_from, best_area.z_from)
        stop_world = (best_area.x_to, best_area.z_to)

    start_local = _world_to_best_area_local(start_world[0], start_world[1], best_area)
    stop_local = _world_to_best_area_local(stop_world[0], stop_world[1], best_area)
    start_local = _nearest_walkable(start_local[0], start_local[1], walkable) or start_local
    stop_local = _nearest_walkable(stop_local[0], stop_local[1], walkable) or stop_local
    start_world = _local_to_world(start_local[0], start_local[1], best_area)
    stop_world = _local_to_world(stop_local[0], stop_local[1], best_area)

    def add_path(from_local: Tuple[int, int], to_local: Tuple[int, int]) -> None:
        p = find_path(walkable, heightmap_local, from_local, to_local)
        if p is None:
            return
        for (li, lj) in p:
            wx, wz = _local_to_world(li, lj, best_area)
            path_cells.add((wx, wz))

    if len(buildings) == 0:
        pass
    elif len(buildings) == 1:
        path_cells.add(fronts_world[0])
        add_path(start_local, fronts_local[0])
        add_path(fronts_local[0], stop_local)
    else:
        # Path: start corner -> nearest building front, MST between fronts, nearest front -> stop corner
        mst_edges = _mst_edges(fronts_world)
        for (i, j) in mst_edges:
            add_path(fronts_local[i], fronts_local[j])
        # Start -> nearest front (by path length)
        best_start_front = None
        best_start_len = float("inf")
        for idx in range(len(fronts_local)):
            p = find_path(walkable, heightmap_local, start_local, fronts_local[idx])
            if p is not None and len(p) < best_start_len:
                best_start_len = len(p)
                best_start_front = idx
        if best_start_front is not None:
            add_path(start_local, fronts_local[best_start_front])
        # Stop -> nearest front
        best_stop_front = None
        best_stop_len = float("inf")
        for idx in range(len(fronts_local)):
            p = find_path(walkable, heightmap_local, stop_local, fronts_local[idx])
            if p is not None and len(p) < best_stop_len:
                best_stop_len = len(p)
                best_stop_front = idx
        if best_stop_front is not None:
            add_path(stop_local, fronts_local[best_stop_front])

    # Expand to path_width x path_width (e.g. 3x3), never on building footprints
    building_footprints = _building_footprint_set(buildings, best_area)
    path_cells = _expand_path_to_width(path_cells, path_width, best_area, building_footprints)

    # Place path blocks path_y_below blocks below surface (village-style paths),
    # but switch to oak planks when the column is water (bridge-like behavior).
    for (wx, wz) in path_cells:
        li_global = wx - build_area.x_from
        lj_global = wz - build_area.z_from
        if 0 <= li_global < world.heightmap_ground.shape[0] and 0 <= lj_global < world.heightmap_ground.shape[1]:
            y_surface = int(world.heightmap_ground[li_global, lj_global])
            # Decide material based on whether this column is water.
            if _is_water_column(world, li_global, lj_global):
                # Bridge: place oak planks where we would normally place the path.
                material = "minecraft:oak_planks"
            else:
                material = path_block

            y = max(0, y_surface - path_y_below)
            editor.placeBlock((wx, y, wz), Block(material))
