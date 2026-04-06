from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from data.build_area import BuildArea
from data.settlement_entities import Building, Districts, Plot, RoadCell


# ---------------------------------------------------------------------------
# OccupancyMap
# ---------------------------------------------------------------------------

class OccupancyMap:
    """
    Single source of truth for all occupied world cells.

    Maintains a world-coord set (for O(1) membership tests) and a
    local-index numpy mask (for fast numpy-slice checks in PlotPlanner)
    in sync at all times.

    Every module that claims space in the settlement — plaza, roads,
    fountains, tower, plot footprints — writes here.  Nothing else
    should track occupancy independently.
    """

    def __init__(self, best_area: BuildArea) -> None:
        self._area  = best_area
        self._cells: set[tuple[int, int]] = set()
        self._mask  = np.zeros((best_area.width, best_area.depth), dtype=bool)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, cells: Iterable[tuple[int, int]]) -> None:
        """Mark world-coord XZ cells as occupied."""
        for wx, wz in cells:
            if (wx, wz) in self._cells:
                continue
            self._cells.add((wx, wz))
            try:
                li, lj = self._area.world_to_index(wx, wz)
                self._mask[li, lj] = True
            except ValueError:
                pass  # outside best_area — track in set only

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def blocked(self, li: int, lj: int, w: int, d: int) -> bool:
        """True if any cell in the local-index rectangle is occupied."""
        return bool(self._mask[li:li + w, lj:lj + d].any())

    def __contains__(self, cell: tuple[int, int]) -> bool:
        return cell in self._cells

    def __iter__(self):
        return iter(self._cells)

    def __len__(self) -> int:
        return len(self._cells)


# ---------------------------------------------------------------------------
# SettlementState
# ---------------------------------------------------------------------------

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
    occupancy   — updated after every phase that claims space:
                    plaza → district markers → tower → roads → plots
    plots       — populated by plan_plots()
    buildings   — populated incrementally during structure placement
    """

    center:    tuple[int, int] | None = None
    districts: Districts | None       = None

    # Central plaza — set after plaza placement (None if settlement is too small)
    plaza_center: tuple[int, int] | None = None
    plaza_radius: int                    = 0

    # Road cells — full RoadCell objects for type queries
    roads: set[RoadCell] = field(default_factory=set)

    # O(1) coordinate lookup — mirrors roads but strips type
    _road_coords: set[tuple[int, int]] = field(default_factory=set)

    # Universal occupancy — every module that places something writes here.
    # Replaces the old `taken` set; also replaces PlotPlanner._taken_mask.
    # Initialised lazily via init_occupancy() once best_area is known.
    occupancy: OccupancyMap | None = field(default=None)

    plots:     list[Plot]     = field(default_factory=list)
    buildings: list[Building] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def init_occupancy(self, best_area: BuildArea) -> None:
        """Call once after world analysis to attach the OccupancyMap."""
        self.occupancy = OccupancyMap(best_area)

    # ------------------------------------------------------------------
    # Occupancy helpers (keep call sites unchanged where possible)
    # ------------------------------------------------------------------

    def add_taken(self, cells: Iterable[tuple[int, int]]) -> None:
        """Register arbitrary world cells as occupied."""
        self.occupancy.add(cells)

    def add_road_cells(self, cells: Iterable[RoadCell]) -> None:
        """Add road cells and register them in occupancy."""
        for cell in cells:
            self.roads.add(cell)
            self._road_coords.add((cell.x, cell.z))
        self.occupancy.add((cell.x, cell.z) for cell in cells)

    def add_plot(self, plot: Plot) -> None:
        """Append a validated plot and mark its footprint as occupied."""
        self.plots.append(plot)
        self.occupancy.add(
            (plot.x + dx, plot.z + dz)
            for dx in range(plot.width)
            for dz in range(plot.depth)
        )

    def add_building(self, building: Building) -> None:
        """Append a placed building."""
        self.buildings.append(building)

    def has_road(self, x: int, z: int) -> bool:
        """Return True if (x, z) is part of the road network (any type). O(1)."""
        return (x, z) in self._road_coords

    def get_road_type(self, x: int, z: int) -> str | None:
        """Return the road type at (x, z), or None. O(n)."""
        for cell in self.roads:
            if cell.x == x and cell.z == z:
                return cell.type
        return None

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
        occ = len(self.occupancy) if self.occupancy else 0
        return (
            f"SettlementState("
            f"center={self.center}, "
            f"districts={len(self.districts.district_list) if self.districts else 0}, "
            f"roads={self.road_cell_count}, "
            f"occupied={occ}, "
            f"plots={self.plot_count}, "
            f"buildings={self.building_count})"
        )
