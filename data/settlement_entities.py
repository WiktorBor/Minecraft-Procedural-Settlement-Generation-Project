from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import Voronoi


# ---------------------------------------------------------------------------
# Shared spatial base
# ---------------------------------------------------------------------------

@dataclass
class RectangularArea:
    """
    Base for any axis-aligned rectangular entity in world XZ coordinates.

    Exposes x_from/x_to/z_from/z_to so all subclasses satisfy the
    HasBounds protocol defined in utils/geometry.py.
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
        """World X coordinate of the centre of this area."""
        return self.x + self.width / 2

    @property
    def center_z(self) -> float:
        """World Z coordinate of the centre of this area."""
        return self.z + self.depth / 2


# ---------------------------------------------------------------------------
# Domain entities
# ---------------------------------------------------------------------------

@dataclass
class Plot(RectangularArea):
    """
    A rectangular building plot in world coordinates.

    (x, z) is the minimum-X, minimum-Z corner.
    y is the ground level used for vertical placement.
    type matches the district type that owns this plot.
    facing is the cardinal direction ("north"/"south"/"east"/"west") of the
    plot's front edge — the edge that points toward the nearest road cell.
    """
    y:      int = 0
    type:   str = ""
    facing: str = "south"

    def front_door(self) -> tuple[int, int]:
        """
        World (x, z) of the cell one block outside the centre of the front edge.
        This is where the connector path should end.
        """
        cx = int(self.center_x)
        cz = int(self.center_z)
        if self.facing == "north":
            return cx, self.z_from - 1
        if self.facing == "south":
            return cx, self.z_to + 1
        if self.facing == "west":
            return self.x_from - 1, cz
        return self.x_to + 1, cz  # east


@dataclass
class Building(RectangularArea):
    """
    A placed building instance in the world.

    Shares the spatial interface with Plot so geometry helpers work
    on either without special-casing.
    """
    y:      int = 0
    type:   str = ""
    facing: str = "south"

    def front_door(self) -> tuple[int, int]:
        """World (x, z) one block outside the centre of the front edge."""
        cx = int(self.center_x)
        cz = int(self.center_z)
        if self.facing == "north":
            return cx, self.z_from - 1
        if self.facing == "south":
            return cx, self.z_to + 1
        if self.facing == "west":
            return self.x_from - 1, cz
        return self.x_to + 1, cz  # east


@dataclass(frozen=True)
class RoadCell:
    """
    A single immutable cell in the road network.

    Frozen so instances can be used as dict keys or set members.
    type defaults to 'main_road' so RoadCell(x, z) works for lookups.
    """
    x:    int
    z:    int
    type: str = "main_road"


@dataclass
class District(RectangularArea):
    """
    A district region within the settlement defined by its bounding rectangle.

    centre_x / centre_z are inherited from RectangularArea and are always
    derived from (x, width) and (z, depth) — never stored separately.
    """
    type: str = ""


@dataclass
class Districts:
    """
    All district data produced by the district planner.

    Attributes
    ----------
    map : np.ndarray, shape (width, depth), dtype int32
        Per-cell district index. -1 = unassigned.
    types : dict[int, str]
        Maps district index → district type string.
    seeds : np.ndarray, shape (N, 2), dtype float32
        XZ seed coordinates (local index space) used to build the Voronoi.
    voronoi : scipy.spatial.Voronoi
        The Voronoi diagram over the seed points.
    district_list : list[District]
        District objects in index order (index matches types keys).
    """
    map:           np.ndarray
    types:         dict[int, str]
    seeds:         np.ndarray
    voronoi:       Voronoi
    district_list: list[District] = field(default_factory=list)

    def get_at(self, world_x: int, world_z: int, analysis) -> int:
        """
        Converts world coordinates to local map indices and returns 
        the district index at that location.
        """
        try:
            # Convert world XZ to local array indices (0 to width/depth)
            li, lj = analysis.best_area.world_to_index(world_x, world_z)
            return self.map[li, lj]
        except (IndexError, ValueError):
            return -1