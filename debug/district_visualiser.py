"""
district_visualiser.py
======================
Debug tool: renders the district layout directly in Minecraft so you can
see what the district planner produced *before* roads are placed.

What it draws
-------------
- Each district's Voronoi region painted with a unique wool colour (one
  block above ground so it floats visibly above any terrain).
- The district centre marked with a tall beacon-style pillar (glass +
  coloured wool on top) so centres are easy to spot from above.
- A road-connection preview: thin lines of white wool connecting district
  centres along the MST edges that road_planner.py would follow, so you
  can see immediately if any centre is in a bad position.
- Console log with each district's index, type, centre coordinates, and
  the wool colour used — handy to cross-reference with the Minecraft view.

Usage
-----
Call `visualise_districts()` after you have an Analysis and Districts object
but *before* calling RoadPlanner.generate().  It is a pure debug helper and
does NOT modify any planner state.

    from debug.district_visualiser import visualise_districts
    visualise_districts(editor, analysis, districts)

Colour scheme
-------------
District type  → wool colour
residential    → orange
farming        → lime
fishing        → cyan
forest         → green
mining         → gray
commercial     → yellow
industrial     → brown
decoration     → pink
(fallback)     → purple
"""

from __future__ import annotations

import logging

from gdpc import Block
from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Districts
from utils.mst import mst_edges          # same helper road_planner uses

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour map: district type → Minecraft wool colour
# ---------------------------------------------------------------------------
_WOOL: dict[str, str] = {
    "residential": "orange_wool",
    "farming":     "lime_wool",
    "fishing":     "cyan_wool",
    "forest":      "green_wool",
    "mining":      "gray_wool",
    "commercial":  "yellow_wool",
    "industrial":  "brown_wool",
    "decoration":  "pink_wool",
}
_FALLBACK_WOOL = "purple_wool"

# Height offset above ground for the district fill layer
_FILL_Y_OFFSET  = 20   # 1 block above ground → clearly visible, easy to remove
_PILLAR_HEIGHT  = 8   # how tall the centre pillar is
_ROAD_Y_OFFSET  = 2   # road-preview lines sit 2 above ground


def _wool(district_type: str) -> str:
    return _WOOL.get(district_type.strip().lower(), _FALLBACK_WOOL)


def visualise_districts(
    editor: Editor,
    analysis: WorldAnalysisResult,
    districts: Districts,
    draw_region_fill: bool = True,
    draw_centre_pillars: bool = True,
    draw_mst_preview: bool = True,
) -> None:
    """
    Paint the district layout into Minecraft for debugging.

    Parameters
    ----------
    editor              : GDPC editor (buffered writes are fine).
    analysis            : WorldAnalysisResult with heightmap and best_area.
    districts           : Districts produced by DistrictPlanner.generate().
    draw_region_fill    : Paint every cell of each Voronoi region with wool.
    draw_centre_pillars : Place a tall glass+wool pillar at each centre.
    draw_mst_preview    : Draw thin wool lines along MST edges (road preview).
    """
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground
    dmap      = districts.map          # (W, D) int32 — district index per cell
    n         = len(districts.district_list)

    logger.info("Districts=%d  area x[%d,%d] z[%d,%d]", n, area.x_from, area.x_to, area.z_from, area.z_to)

    # ------------------------------------------------------------------
    # 1. Region fill
    # ------------------------------------------------------------------
    if draw_region_fill:

        W, D = dmap.shape
        for li in range(W):
            for lj in range(D):
                idx   = int(dmap[li, lj])
                dtype = districts.types.get(idx, "residential")
                wx, wz = area.index_to_world(li, lj)
                wy     = int(heightmap[li, lj]) + _FILL_Y_OFFSET
                editor.placeBlock((wx, wy, wz), Block(f"minecraft:{_wool(dtype)}"))

    # ------------------------------------------------------------------
    # 2. Centre pillars
    # ------------------------------------------------------------------
    if draw_centre_pillars:

        for idx, district in enumerate(districts.district_list):
            cx = int(district.center_x)
            cz = int(district.center_z)
            dtype = districts.types.get(idx, "residential")
            wool_id = _wool(dtype)

            if not area.contains_xz(cx, cz):
                logger.warning("  District %d centre outside area — skipping pillar.", idx)
                continue

            li, lj = area.world_to_index(cx, cz)
            cy = int(heightmap[li, lj]) + _FILL_Y_OFFSET

            # Glass shaft
            for dy in range(_PILLAR_HEIGHT - 1):
                editor.placeBlock((cx, cy + dy, cz), Block("minecraft:glass"))

            # Wool top — coloured cap so you can see the type from a distance
            top_y = cy + _PILLAR_HEIGHT - 1
            editor.placeBlock((cx, top_y,     cz), Block(f"minecraft:{wool_id}"))
            editor.placeBlock((cx, top_y + 1, cz), Block(f"minecraft:{wool_id}"))

            logger.info(
                "  District %2d  type=%-12s  centre=(%d, %d, %d)  colour=%s",
                idx, dtype, cx, cy, cz, wool_id,
            )

    # ------------------------------------------------------------------
    # 3. MST road preview (white wool centre-lines)
    # ------------------------------------------------------------------
    if draw_mst_preview:

        connection_points = [
            (d.center_x, d.center_z) for d in districts.district_list
        ]
        edges = mst_edges(connection_points)

        for u, v in edges:
            (sx, sz), (gx, gz) = connection_points[u], connection_points[v]
            sx, sz, gx, gz = int(sx), int(sz), int(gx), int(gz)

            # Simple Bresenham line between the two centres
            for wx, wz in _bresenham(sx, sz, gx, gz):
                if not area.contains_xz(wx, wz):
                    continue
                li, lj = area.world_to_index(wx, wz)
                wy = int(heightmap[li, lj]) + _ROAD_Y_OFFSET
                editor.placeBlock((wx, wy, wz), Block("minecraft:white_wool"))

    editor.flushBuffer()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bresenham(
    x0: int, z0: int, x1: int, z1: int
) -> list[tuple[int, int]]:
    """Integer Bresenham line from (x0,z0) to (x1,z1)."""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0);  sx = 1 if x0 < x1 else -1
    dz = abs(z1 - z0);  sz = 1 if z0 < z1 else -1
    err = dx - dz

    while True:
        points.append((x0, z0))
        if x0 == x1 and z0 == z1:
            break
        e2 = 2 * err
        if e2 > -dz:
            err -= dz
            x0  += sx
        if e2 < dx:
            err += dx
            z0  += sz

    return points


# ---------------------------------------------------------------------------
# Legend helper (optional — call this to log a colour key to the console)
# ---------------------------------------------------------------------------

def print_legend() -> None:
    """Print the colour → district type legend to stdout."""
    print("\n=== District Visualiser Legend ===")
    for dtype, wool in _WOOL.items():
        colour = wool.replace("_wool", "").upper()
        print(f"  {colour:<12} → {dtype}")
    print(f"  {'PURPLE':<12} → (other / fallback)")
    print()