from __future__ import annotations

from structures.base.structure import Structure
from .house.house import House

__all__ = ["STRUCTURES", "get_structure"]

STRUCTURES: dict[str, type[Structure]] = {
    "house": House,
}


def get_structure(structure_type: str) -> type[Structure]:
    """
    Look up a Structure class by type string.

    Args:
        structure_type: Key into STRUCTURES (e.g. 'house').

    Raises:
        KeyError: If the type is not registered, with a helpful message
                  listing valid options.
    """
    if structure_type not in STRUCTURES:
        raise KeyError(
            f"Unknown structure type {structure_type!r}. "
            f"Registered types: {sorted(STRUCTURES)}"
        )
    return STRUCTURES[structure_type]