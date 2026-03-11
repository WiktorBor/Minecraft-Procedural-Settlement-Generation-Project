from dataclasses import dataclass, field
from typing import Optional, Tuple, List

from .settlement_entities import Plot, RoadCell, District, Building


@dataclass
class SettlementState:
    """
    Stores the evolving state of the settlement.
    All coordinates are world (x, z).
    """

    # settlement center
    center: Optional[Tuple[int, int]] = None

    # roads
    roads: List[RoadCell] = field(default_factory=list)

    # plots
    plots: List[Plot] = field(default_factory=list)

    # districts
    districts: List[District] = field(default_factory=list)

    # buildings
    buildings: List[Building] = field(default_factory=list)