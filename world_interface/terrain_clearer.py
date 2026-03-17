import numpy as np
from scipy.ndimage import label
from gdpc import Block
from data.configurations import TerrainConfig
from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Plot
from typing import Any

def clear_area(editor: Any, analysis: WorldAnalysisResult, plot: Plot, buffer=3) -> None:
    """
    Clears vegetation in a circular area around a building area.

    Parameters
    ----------
    editor : Editor
        The world editor object.
    analysis : WorldAnalysisResult
        Contains heightmaps for terrain reference.
    building_area : BuildArea
        The area to clear.
    buffer : int
        Extra blocks around the building to clear.
    """
    # center of the building area in world coordinates
    center_x = (plot.x + plot.x + plot.width) // 2
    center_z = (plot.z + plot.z + plot.depth) // 2
    config = TerrainConfig()

    width = plot.width
    depth = plot.depth

    radius = max(width, depth) // 2 + buffer
    radius_sq = radius ** 2

    for x in range(center_x - radius, center_x + radius + 1):
        for z in range(center_z - radius, center_z + radius + 1):

            if (x - center_x) ** 2 + (z - center_z) ** 2 > radius_sq:
                continue

            gx = x - analysis.best_area.x_from
            gz = z - analysis.best_area.z_from

            if not (0 <= gx < analysis.heightmap_ground.shape[0] and
                    0 <= gz < analysis.heightmap_ground.shape[1]):
                continue

            ground = int(analysis.heightmap_ground[gx, gz])
            surface = int(analysis.heightmap_surface[gx, gz])

            for y in range(ground, surface + 1):
                block = editor.getBlock((x, y, z))
                block_id = block.id.lower()

                if any(v in block_id for v in config.VEGETATION_BLOCK_KEYWORDS):
                    editor.placeBlock((x, y, z), Block("minecraft:air"))


def remove_sparse_top(editor, analysis, min_cluster_size=6):
    """
    Remove small clusters of blocks that stick up above the terrain.
    """

    area = analysis.best_area
    heightmap = analysis.heightmap_ground

    ix0, iz0 = area.world_to_index(area.x_from, area.z_from)
    ix1, iz1 = area.world_to_index(area.x_to, area.z_to)

    submap = heightmap[ix0:ix1+1, iz0:iz1+1]

    w, d = submap.shape

    # Detect blocks that are higher than neighbors
    bump_mask = np.zeros_like(submap, dtype=bool)

    for x in range(1, w-1):
        for z in range(1, d-1):

            h = submap[x, z]

            neighbors = [
                submap[x+1, z],
                submap[x-1, z],
                submap[x, z+1],
                submap[x, z-1],
            ]

            if h > max(neighbors):
                bump_mask[x, z] = True

    # Group bumps
    labeled, num = label(bump_mask)

    for cluster_id in range(1, num + 1):

        cells = np.argwhere(labeled == cluster_id)

        if len(cells) < min_cluster_size:

            for cx, cz in cells:

                wx, wz = area.index_to_world(cx, cz)
                y = int(submap[cx, cz])

                # Remove the top block
                editor.placeBlock((wx, y, wz), Block("air"))

                # Update heightmap
                heightmap[ix0 + cx, iz0 + cz] -= 1