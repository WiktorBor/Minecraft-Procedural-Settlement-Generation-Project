"""
utils/interfaces.py
-------------------
Structural protocols (PEP 544) for the external interfaces that analysis/
and other mid-layer modules depend on.

Keeping protocols in utils/ means analysis/ can depend on the *shape* of
a terrain loader without importing the concrete world_interface implementation,
satisfying the dependency rule:

    analysis/ → utils/ → data/     

The concrete TerrainLoader in world_interface/ must satisfy this protocol.
"""
from __future__ import annotations

from typing import Any, Protocol

from data.build_area import BuildArea


class TerrainLoaderProtocol(Protocol):
    """
    Structural interface for any object that can load terrain data from the
    world (GDMC HTTP API, a mock, a replay, etc.).

    All analysis/ and planning/ code depends on this protocol, never on the
    concrete TerrainLoader from world_interface/.
    """

    def get_build_area(self) -> BuildArea:
        """Return the active build area."""
        ...

    def get_heightmap(
        self,
        x: int,
        z: int,
        width: int,
        depth: int,
        heightmap_type: str,
    ) -> Any:
        """
        Return a heightmap array for the given region.

        heightmap_type is one of the GDMC heightmap identifiers:
        "MOTION_BLOCKING", "MOTION_BLOCKING_NO_PLANTS", "OCEAN_FLOOR", etc.
        """
        ...

    def get_biomes(
        self,
        x: int,
        z: int,
        width: int,
        depth: int,
    ) -> Any:
        """Return biome data for the given region."""
        ...

    def get_blocks(
        self,
        x: int,
        y: int,
        z: int,
        width: int,
        height: int,
        depth: int,
    ) -> list[dict]:
        """Return a list of block dicts for the given 3-D region."""
        ...