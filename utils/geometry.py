from typing import Any
import numpy as np

def center_distance(area_a: Any, area_b: Any):
    acx = (area_a.x_from + area_a.x_to) / 2
    acz = (area_a.z_from + area_a.z_to) / 2
    bcx = (area_b.x_from + area_b.x_to) / 2
    bcz = (area_b.z_from + area_b.z_to) / 2
    return np.sqrt((acx - bcx)**2 + (acz - bcz)**2)