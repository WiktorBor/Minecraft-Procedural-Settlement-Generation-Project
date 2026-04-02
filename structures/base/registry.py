"""
Central registry of buildable structure types.

All structure builders are registered here via _build_registry() in
structure_selector.py — this module exposes a convenience lookup used
by any code that needs to query available structures without instantiating
a full StructureSelector.
"""
from __future__ import annotations

from structures.base.structure import Structure
from structures.house.house import House

__all__ = ["STRUCTURES", "get_structure"]

# Structures that inherit from the Structure base class.
# Expand as remaining structures adopt the base class.
STRUCTURES: dict[str, type[Structure]] = {
    "house":   House,
}

# Plot building keys — placed inside the settlement on regular plots.
ALL_TEMPLATE_KEYS: frozenset[str] = frozenset({
    "cottage",
    "tower_house",    # tall house variant — plot building, not fortification
    "blacksmith",
    "plaza",
    "market_stall",
    "clock_tower",
    "tavern",
    "farm",
    "decoration",
})

# Fortification-only keys — placed by FortificationBuilder on the perimeter.
FORTIFICATION_KEYS: frozenset[str] = frozenset({
    "tower",          # corner towers
    "fortification",  # wall segments
})

# Centroid-placement keys — placed once at a fixed location, never in pools.
CENTROID_KEYS: frozenset[str] = frozenset({
    "spire_tower",    # placed at best_area centre by settlement_generator
})


def get_structure(structure_type: str) -> type[Structure]:
    """Look up a Structure subclass by type string."""
    if structure_type not in STRUCTURES:
        raise KeyError(
            f"Unknown structure type {structure_type!r}. "
            f"Registered: {sorted(STRUCTURES)}"
        )
    return STRUCTURES[structure_type]