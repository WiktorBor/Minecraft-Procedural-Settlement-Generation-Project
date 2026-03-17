import numpy as np

def get_area_slices(build_area, area, map) -> np.ndarray:
    ix_start, iz_start = build_area.world_to_index(area.x_from, area.z_from)
    ix_end, iz_end = area.width - 1, area.depth - 1

    # Clamp to map bounds
    ix_end = min(ix_end, map.shape[0]-1)
    iz_end = min(iz_end, map.shape[1]-1)
    
    return map[ix_start: ix_start + ix_end+1, iz_start: iz_start + iz_end+1]