from __future__ import annotations

import numpy as np


def build_walkable_grid(
    local_water: np.ndarray,
    additional_blocked: np.ndarray | None = None,
) -> np.ndarray:
    """
    Build a boolean walkability grid from terrain data.

    A cell is walkable if it is not water (and not in any additional blocked mask).

    Args:
        local_water: 2-D array where True (or non-zero) indicates a water cell.
        additional_blocked: Optional 2-D boolean array of the same shape for
                            any extra blocked cells (steep slopes, occupied plots,
                            etc.).  Combined with water via logical OR.

    Returns:
        2-D boolean array of the same shape; True = walkable.
    """
    walkable = ~np.asarray(local_water, dtype=bool)   # no copy if already bool

    if additional_blocked is not None:
        walkable &= ~np.asarray(additional_blocked, dtype=bool)

    return walkable