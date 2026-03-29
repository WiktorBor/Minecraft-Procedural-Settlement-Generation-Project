from __future__ import annotations
from dataclasses import dataclass


@dataclass
class BuildArea:
    """
    Axis-aligned 3-D region representing the active build area.

    Bounds are inclusive on all sides.
    Satisfies the HasBounds protocol defined in utils/geometry.py.
    """

    x_from: int
    y_from: int
    z_from: int
    x_to:   int
    y_to:   int
    z_to:   int

    # ------------------------------------------------------------------
    # Dimensions
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        """Extent along the X axis (inclusive)."""
        return self.x_to - self.x_from + 1

    @property
    def depth(self) -> int:
        """Extent along the Z axis (inclusive)."""
        return self.z_to - self.z_from + 1

    @property
    def height(self) -> int:
        """Extent along the Y axis (inclusive)."""
        return self.y_to - self.y_from + 1

    # ------------------------------------------------------------------
    # Containment checks
    # ------------------------------------------------------------------

    def contains(self, x: int, y: int, z: int) -> bool:
        """Return True if the world coordinate (x, y, z) is inside this area."""
        return (
            self.x_from <= x <= self.x_to
            and self.y_from <= y <= self.y_to
            and self.z_from <= z <= self.z_to
        )

    def contains_xz(self, x: int, z: int) -> bool:
        """Return True if the XZ world coordinate lies within this area."""
        return self.x_from <= x <= self.x_to and self.z_from <= z <= self.z_to

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def world_to_index(self, x: int, z: int) -> tuple[int, int]:
        """
        Convert world XZ coordinates to local (i, j) array indices.

        Raises
        ------
        ValueError
            If (x, z) lies outside the build area.
        """
        if not self.contains_xz(x, z):
            raise ValueError(
                f"World coordinate ({x}, {z}) is outside build area "
                f"x=[{self.x_from}, {self.x_to}] z=[{self.z_from}, {self.z_to}]"
            )
        return x - self.x_from, z - self.z_from

    def index_to_world(self, i: int, j: int) -> tuple[int, int]:
        """
        Convert local (i, j) array indices to world XZ coordinates.

        Raises
        ------
        ValueError
            If (i, j) is out of bounds for this build area.
        """
        if i < 0 or j < 0 or i >= self.width or j >= self.depth:
            raise ValueError(
                f"Index ({i}, {j}) is outside build area indices "
                f"[0, {self.width}) x [0, {self.depth})"
            )
        return self.x_from + i, self.z_from + j

    def __str__(self) -> str:
        return (
            f"BuildArea("
            f"x=[{self.x_from}, {self.x_to}], "
            f"y=[{self.y_from}, {self.y_to}], "
            f"z=[{self.z_from}, {self.z_to}] "
            f"| {self.width}×{self.height}×{self.depth})"
        )