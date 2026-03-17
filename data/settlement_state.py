from dataclasses import dataclass, field
from typing import Optional, Tuple, List

from .settlement_entities import Plot, RoadCell, Districts, Building


@dataclass
class SettlementState:
    """
    Stores the evolving state of the settlement.
    All coordinates are world (x, z).
    To access heightmaps or grids, 
    convert using BuildArea.world_to_index(x, z) to get local (i, j) indices.
    """

    # settlement center in world coordinates (x, z)
    center: Optional[Tuple[int, int]] = None

    # roads are stored as a list of RoadCell in world coordinates
    roads: List[RoadCell] = field(default_factory=list)

    # plots in world coordinates
    plots: List[Plot] = field(default_factory=list)

    # districts (logical groupings of plots) with their own map and types
    districts: Optional[Districts] = None

    # buildings in world coordinates
    buildings: List[Building] = field(default_factory=list)