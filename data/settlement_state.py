from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from data.settlement_entities import Building, Districts, Plot, RoadCell


@dataclass
class SettlementState:
    """
    Evolving state of the settlement during generation.

    All coordinates are world (x, z). Use BuildArea.world_to_index(x, z)
    to obtain local (i, j) array indices when accessing heightmaps.

    Lifecycle
    ---------
    center      — None until the site locator has run
    districts   — None until the district planner has run
    roads       — populated by plan_roads()
    taken       — fountains registered first, then roads appended automatically
    plots       — populated by plan_plots() after roads are known
    buildings   — populated incrementally during structure placement
    """

    center:    tuple[int, int] | None = None
    districts: Districts | None       = None

    # Road cells — full RoadCell objects for type queries
    roads: set[RoadCell] = field(default_factory=set)

    # O(1) coordinate lookup — mirrors roads but strips type
    _road_coords: set[tuple[int, int]] = field(default_factory=set)

    # All world (x, z) cells physically occupied (fountains + roads + buildings)
    # PlotPlanner reads this to avoid placing plots on taken ground.
    taken: set[tuple[int, int]] = field(default_factory=set)

    plots:     list[Plot]     = field(default_factory=list)
    buildings: list[Building] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_taken(self, cells: Iterable[tuple[int, int]]) -> None:
        """Register arbitrary world cells as occupied (fountains, markers, etc.)."""
        self.taken.update(cells)

    def add_road_cells(self, cells: Iterable[RoadCell]) -> None:
        """
        Add road cells to the network.

        Also registers each cell into taken so plot planning
        automatically avoids road footprints.
        """
        for cell in cells:
            self.roads.add(cell)
            self._road_coords.add((cell.x, cell.z))
            self.taken.add((cell.x, cell.z))

    def add_plot(self, plot: Plot) -> None:
        """Append a validated plot."""
        self.plots.append(plot)

    def add_building(self, building: Building) -> None:
        """Append a placed building."""
        self.buildings.append(building)

    # ------------------------------------------------------------------
    # Road queries
    # ------------------------------------------------------------------

    def has_road(self, x: int, z: int) -> bool:
        """Return True if (x, z) is part of the road network (any type). O(1)."""
        return (x, z) in self._road_coords

    def get_road_type(self, x: int, z: int) -> str | None:
        """
        Return the road type at (x, z), or None if no road is present.

        O(n) — only call when the type is actually needed (e.g. road builder).
        """
        for cell in self.roads:
            if cell.x == x and cell.z == z:
                return cell.type
        return None

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_placed(self) -> bool:
        """True once a settlement centre has been chosen."""
        return self.center is not None

    @property
    def plot_count(self) -> int:
        return len(self.plots)

    @property
    def building_count(self) -> int:
        return len(self.buildings)

    @property
    def road_cell_count(self) -> int:
        return len(self.roads)

    def __str__(self) -> str:
        return (
            f"SettlementState("
            f"center={self.center}, "
            f"districts={len(self.districts.district_list) if self.districts else 0}, "
            f"roads={self.road_cell_count}, "
            f"plots={self.plot_count}, "
            f"buildings={self.building_count})"
        )