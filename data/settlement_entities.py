from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from scipy.spatial import Voronoi


# ---------------------------------------------------------------------------
# Protocol — shared spatial interface (compatible with HasBounds in geometry.py)
# ---------------------------------------------------------------------------

@dataclass
class RectangularArea:
    """
    Base for any axis-aligned rectangular entity in world XZ coordinates.

    Exposes x_from/x_to/z_from/z_to so all subclasses satisfy the
    HasBounds protocol defined in utils/geometry.py, enabling use of
    center_distance(), areas_overlap(), and area_contains_point().
    """
    x:     int   # min-X corner (world coordinate)
    z:     int   # min-Z corner (world coordinate)
    width: int   # extent along X (blocks)
    depth: int   # extent along Z (blocks)

    @property
    def x_from(self) -> int:
        return self.x

    @property
    def x_to(self) -> int:
        return self.x + self.width - 1

    @property
    def z_from(self) -> int:
        return self.z

    @property
    def z_to(self) -> int:
        return self.z + self.depth - 1

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_z(self) -> float:
        return self.z + self.depth / 2


# ---------------------------------------------------------------------------
# Domain entities
# ---------------------------------------------------------------------------

@dataclass
class Plot(RectangularArea):
    """
    A rectangular plot in world coordinates.

    The (x, z) corner is the minimum-X, minimum-Z point of the plot.
    `y` is the ground level (used for vertical placement).
    """
    y:    int = 0    # ground level (Y world coordinate)
    type: str = ""


@dataclass
class Building(RectangularArea):
    """
    A placed building instance in the world.

    Shares the spatial interface with Plot so geometry helpers can operate
    on either without special-casing.
    """
    y:    int = 0    # ground level (Y world coordinate)
    type: str = ""


@dataclass(frozen=True)
class RoadCell:
    """
    A single immutable cell in the road network.

    Frozen so instances can be used as dict keys or set members.
    """
    x: int
    z: int


@dataclass
class District(RectangularArea):
    """
    A district region within the settlement, defined by its bounding rectangle.

    The centre is derived from corner + dimensions and is never stored
    separately to avoid the risk of stale values.
    """
    type: str = ""


@dataclass
class Districts:
    """
    All district-related data produced by the district planner.

    Attributes
    ----------
    map : np.ndarray, shape (width, depth), dtype int32
        Per-cell district index (-1 = unassigned).
    types : dict[int, str]
        Maps district index → district type string.
    seeds : np.ndarray, shape (N, 2), dtype float32
        XZ seed coordinates used to generate the Voronoi diagram.
    voronoi : scipy.spatial.Voronoi
        The Voronoi diagram over the seed points.
    district_list : list[District]
        Ordered list of District objects (index matches `types` keys).
    """
    map:           np.ndarray
    types:         dict[int, str]
    seeds:         np.ndarray
    voronoi:       Voronoi
    district_list: list[District] = field(default_factory=list)