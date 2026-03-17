from gdpc.editor import Editor
import numpy as np

def terraform_area_real_time(editor: Editor, heightmap: np.ndarray, best_area, max_slope: float = 0.5, block_type: str = "dirt"):
    """
    Smooth small bumps within best_area in real time by editing blocks in the world.

    Args:
        editor: GDPC Editor instance
        heightmap: 2D numpy array of terrain heights
        best_area: BuildArea object
        max_slope: maximum allowed height difference per block
        block_type: block type to fill smoothed terrain
    """

    # Extract indices of best_area in heightmap
    ix_from, iz_from = best_area.world_to_index(best_area.x_from, best_area.z_from)
    ix_to, iz_to = best_area.world_to_index(best_area.x_to, best_area.z_to)

    # Extract submap
    submap = heightmap[ix_from:ix_to+1, iz_from:iz_to+1]

    # Compute target height (median of the area)
    target_height = int(np.round(np.median(submap)))

    # Compute difference per cell
    diff = target_height - submap
    # Clamp by max_slope to avoid drastic changes
    diff = np.clip(diff, -max_slope, max_slope)

    # Apply changes to submap
    new_heights = submap + diff
    heightmap[ix_from:ix_to+1, iz_from:iz_to+1] = new_heights

    # Place blocks in world
    for i in range(new_heights.shape[0]):
        for j in range(new_heights.shape[1]):
            x, z = best_area.index_to_world(i, j)
            y = int(new_heights[i, j])
            editor.placeBlock((x, y, z), block_type)


from gdpc.editor import Editor
import numpy as np

def terraform_area_real_time(editor: Editor, heightmap: np.ndarray, best_area, max_slope: float = 0.5, block_type: str = "dirt"):
    """
    Smooth small bumps within best_area in real time by editing blocks in the world.

    Args:
        editor: GDPC Editor instance
        heightmap: 2D numpy array of terrain heights
        best_area: BuildArea object
        max_slope: maximum allowed height difference per block
        block_type: block type to fill smoothed terrain
    """

    # Extract indices of best_area in heightmap
    ix_from, iz_from = best_area.world_to_index(best_area.x_from, best_area.z_from)
    ix_to, iz_to = best_area.world_to_index(best_area.x_to, best_area.z_to)

    # Extract submap
    submap = heightmap[ix_from:ix_to+1, iz_from:iz_to+1]

    # Compute target height (median of the area)
    target_height = int(np.round(np.median(submap)))

    # Compute difference per cell
    diff = target_height - submap
    # Clamp by max_slope to avoid drastic changes
    diff = np.clip(diff, -max_slope, max_slope)

    # Apply changes to submap
    new_heights = submap + diff
    heightmap[ix_from:ix_to+1, iz_from:iz_to+1] = new_heights

    # Place blocks in world
    for i in range(new_heights.shape[0]):
        for j in range(new_heights.shape[1]):
            x, z = best_area.index_to_world(i, j)
            y = int(new_heights[i, j])
            editor.placeBlock((x, y, z), block_type)