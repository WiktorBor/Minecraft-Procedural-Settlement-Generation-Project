"""
Central registry of buildable structure types.

Currently not wired into the main pipeline — StructureSelector manages
templates directly. This registry is the intended single source of truth
once all structures inherit from Structure and StructureSelector is refactored.

TODO: make Farm, Tower, Decoration, Tavern, Blacksmith, MarketStall,
      ClockTower, SpireTower inherit from Structure and register them here.
"""
from __future__ import annotations

from structures.base.structure import Structure
from structures.house.house import House

__all__ = ["STRUCTURES", "get_structure"]

# Only House inherits from Structure right now.
# Expand once remaining structures adopt the base class.
STRUCTURES: dict[str, type[Structure]] = {
    "house": House,
}


def get_structure(structure_type: str) -> type[Structure]:
    """Look up a Structure subclass by type string."""
    if structure_type not in STRUCTURES:
        raise KeyError(
            f"Unknown structure type {structure_type!r}. "
            f"Registered: {sorted(STRUCTURES)}"
        )
    return STRUCTURES[structure_type]