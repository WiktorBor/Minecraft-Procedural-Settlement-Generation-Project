from __future__ import annotations

import math
from typing import Protocol


class HasBounds(Protocol):
    """Structural type for any axis-aligned rectangular area."""
    x_from: float
    x_to:   float
    z_from: float
    z_to:   float


def center_distance(area_a: HasBounds, area_b: HasBounds) -> float:
    """
    Euclidean distance between the centres of two axis-aligned rectangles.

    Args:
        area_a: Any object with x_from, x_to, z_from, z_to attributes.
        area_b: Same.

    Returns:
        Distance as a float.
    """
    acx = (area_a.x_from + area_a.x_to) * 0.5
    acz = (area_a.z_from + area_a.z_to) * 0.5
    bcx = (area_b.x_from + area_b.x_to) * 0.5
    bcz = (area_b.z_from + area_b.z_to) * 0.5
    return math.hypot(acx - bcx, acz - bcz)


def areas_overlap(area_a: HasBounds, area_b: HasBounds) -> bool:
    """
    Return True if two axis-aligned rectangles overlap (touching counts).

    Args:
        area_a, area_b: Rectangular areas with x_from/x_to/z_from/z_to.
    """
    return (
        area_a.x_from <= area_b.x_to and area_a.x_to >= area_b.x_from and
        area_a.z_from <= area_b.z_to and area_a.z_to >= area_b.z_from
    )


def area_contains_point(area: HasBounds, x: float, z: float) -> bool:
    """
    Return True if (x, z) lies within the area (inclusive bounds).

    Args:
        area: Rectangular area with x_from/x_to/z_from/z_to.
        x, z: Point coordinates.
    """
    return area.x_from <= x <= area.x_to and area.z_from <= z <= area.z_to