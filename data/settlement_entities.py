from dataclasses import dataclass
import numpy as np
from scipy.spatial import Voronoi
from typing import List, Tuple

@dataclass
class Plot:
    """
    A rectangular plot in world coordinates, 
    defined by its top-left corner (x,z) and its width and depth.
    """
    x: int          # min corner
    y: int          # height (ground level)
    z: int          # min conrer
    width: int
    depth: int
    type: str

@dataclass (frozen=True)
class RoadCell:
    """
    A single cell in a road network
    """
    x: int
    z: int

@dataclass
class District:
    """
    """
    x: int
    z: int
    width: int
    depth: int
    center: Tuple[float, float]
    type: str

@dataclass
class Districts:
    """
    Holds all district-related data including Voronoi diagram.
    """
    map: np.ndarray
    types: dict
    seeds: np.ndarray
    voronoi: Voronoi
    district_list: List[District]

@dataclass
class Building:
    """
    A building instance of the world.
    """
    x: int
    z: int
    width: int
    depth: int
    type: str