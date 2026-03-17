from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .settlement_entities import Plot, RoadCell, Districts, Building


@dataclass
class SettlementState:
    """
    Evolving state of the settlement during generation.

    All coordinates are world (x, z).  To access heightmaps or grids,
    convert with BuildArea.world_to_index(x, z) to obtain local (i, j) indices.

    Lifecycle
    ---------
    `center` is None until the site locator has placed the settlement.
    `districts` is None until the district planner has run.
    All other collections start empty and are populated incrementally.
    """

    # World XZ centre of the settlement — None until site is chosen.
    center: tuple[int, int] | None = None

    # Road cells stored as a set for O(1) membership tests.
    roads: set[RoadCell] = field(default_factory=set)

    # Plots in world coordinates, ordered by insertion.
    plots: list[Plot] = field(default_factory=list)

    # District map and metadata — None until district planner has run.
    districts: Districts | None = None

    # Placed building instances in world coordinates.
    buildings: list[Building] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutation helpers — prefer these over direct collection access
    # ------------------------------------------------------------------

    def add_plot(self, plot: Plot) -> None:
        """Append a plot to the settlement."""
        self.plots.append(plot)

    def add_building(self, building: Building) -> None:
        """Append a building to the settlement."""
        self.buildings.append(building)

    def add_road_cells(self, cells: Iterable[RoadCell]) -> None:
        """Add road cells (duplicates are silently ignored)."""
        self.roads.update(cells)

    def has_road(self, x: int, z: int) -> bool:
        """Return True if (x, z) is part of the road network."""
        return RoadCell(x, z) in self.roads

    # ------------------------------------------------------------------
    # Convenience queries
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
            f"plots={self.plot_count}, "
            f"buildings={self.building_count}, "
            f"road_cells={self.road_cell_count})"
        )