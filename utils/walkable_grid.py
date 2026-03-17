import numpy as np


def build_walkable_grid(local_water: np.ndarray) -> np.ndarray:

    return ~local_water.astype(bool)