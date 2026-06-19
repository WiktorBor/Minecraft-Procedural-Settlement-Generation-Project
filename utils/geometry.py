from __future__ import annotations
import math
from typing import Protocol, runtime_checkable

@runtime_checkable
class HasBounds(Protocol):
    """
    Structural type for any axis-aligned rectangular area.
    Satisfied by BuildArea, Plot, and RectangularArea.
    """
    x_from: float | int
    x_to:   float | int
    z_from: float | int
    z_to:   float | int

def center_distance(area_a: HasBounds, area_b: HasBounds) -> float:
    """Distance between the centers of two rectangular areas."""
    acx = (area_a.x_from + area_a.x_to) * 0.5
    acz = (area_a.z_from + area_a.z_to) * 0.5
    bcx = (area_b.x_from + area_b.x_to) * 0.5
    bcz = (area_b.z_from + area_b.z_to) * 0.5
    return math.hypot(acx - bcx, acz - bcz)

def areas_overlap(area_a: HasBounds, area_b: HasBounds) -> bool:
    """Check if two rectangular areas intersect."""
    return (
        area_a.x_from <= area_b.x_to and
        area_a.x_to   >= area_b.x_from and
        area_a.z_from <= area_b.z_to and
        area_a.z_to   >= area_b.z_from
    )