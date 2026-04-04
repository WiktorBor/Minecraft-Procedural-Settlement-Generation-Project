from __future__ import annotations

import logging

import numpy as np

from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_state import SettlementState
from planning.infrastructure.road_planner import RoadPlanner
from planning.settlement.district_planner import DistrictPlanner
from planning.settlement.plot_planner import PlotPlanner

logger = logging.getLogger(__name__)


class SettlementPlanner:
    """
    Orchestrates district, plot, and road generation to produce a SettlementState.

    Full pipeline (with mid-step world interaction)
    -----------------------------------------------
    1. plan_districts()   — choose centre, generate Voronoi districts.
    2. Caller places fountains and registers their cells into state.taken.
    3. plan_roads(state)  — road network connecting district centres.
    4. Caller places roads in the world (terraforming, block placement).
    5. plan_plots(state)  — building plots validated against all taken tiles.

    Quick pipeline (no fountains, no mid-step world interaction)
    ------------------------------------------------------------
    Call plan() to run steps 1, 3, 5 in one call. Fountains are skipped —
    use this for testing or when fountain placement is not required.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        config: SettlementConfig,
    ) -> None:
        self.analysis = analysis
        self.config   = config

    def plan(self) -> SettlementState:
        """
        Run districts → roads → plots without any mid-step intervention.

        No fountains are placed and no mid-step world interaction occurs.
        For the full pipeline with fountain placement, call plan_districts(),
        register fountain cells into state.taken, then plan_roads(state) and
        plan_plots(state) separately.
        """
        state = self.plan_districts()
        self.plan_roads(state)
        self.plan_plots(state)
        return state

    def plan_districts(self) -> SettlementState:
        """
        Phase 1: choose settlement centre and generate Voronoi districts.

        Returns a SettlementState with centre and districts populated.
        Roads and plots are empty — proceed with fountain placement then
        call plan_roads(state).
        """
        state = SettlementState()

        state.center = self._choose_center()
        logger.info("Settlement centre: %s", state.center)

        # Pre-compute plaza size so DistrictPlanner can exclude the plaza
        # area from district assignment before districts are created.
        # Scale directly from the shortest side of best_area:
        #   radius = short_side // 10, capped at 15.
        #   radius < 3  → settlement too small, no plaza.
        #   radius 3–7  → small plaza (SquareCentre small_fountain style).
        #   radius ≥ 8  → big plaza   (SquareCentre grand_spire style).
        area  = self.analysis.best_area
        w, d  = area.width, area.depth
        plaza_radius = min(min(w, d) // 10, 15)
        if plaza_radius < 3:
            plaza_radius = 0

        if plaza_radius > 0:
            cx_w = (area.x_from + area.x_to) // 2
            cz_w = (area.z_from + area.z_to) // 2
            state.plaza_center = (cx_w, cz_w)
            state.plaza_radius = plaza_radius

            # Exclusion radius covers plaza + gap + ring road outer edge
            road_width   = self.config.road_width
            excl_radius  = plaza_radius + road_width + 1 + road_width // 2
            excl_center  = (w // 2, d // 2)   # local-index centre of best_area
        else:
            excl_center = None
            excl_radius = 0

        logger.info("Planning districts...")
        district_planner = DistrictPlanner(
            analysis=self.analysis,
            config=self.config,
            exclusion_center=excl_center,
            exclusion_radius=excl_radius,
        )
        state.districts = district_planner.generate()
        logger.info("Generated %d districts.", len(state.districts.district_list))

        return state

    def plan_roads(self, state: SettlementState) -> None:
        """
        Phase 3: generate roads connecting district centres.

        Call after plan_districts() and after fountains have been placed and
        registered into state.taken. Roads are added to state.roads and
        state.taken so plot planning sees them as blocked.

        Mutates state in-place.
        """
        logger.info("Planning roads...")
        hub = (
            (float(state.plaza_center[0]), float(state.plaza_center[1]))
            if state.plaza_center is not None
            else None
        )
        road_planner = RoadPlanner(
            analysis=self.analysis,
            districts=state.districts,
            config=self.config,
            hub_point=hub,
        )
        roads = road_planner.generate()
        state.add_road_cells(roads)
        logger.info("Generated %d road cells.", state.road_cell_count)

    def plan_plots(self, state: SettlementState) -> None:
        """
        Phase 5: generate building plots validated against all taken tiles.

        Call after plan_roads() so state.taken contains both fountain and
        road footprints. Mutates state in-place.
        """
        logger.info("Planning plots...")
        plot_planner = PlotPlanner(
            analysis=self.analysis,
            districts=state.districts,
            taken=state.taken,
            config=self.config,
            road_coords=state._road_coords,
        )
        for plot in plot_planner.generate():
            state.add_plot(plot)
        logger.info("Generated %d plots.", state.plot_count)

    def _choose_center(self) -> tuple[int, int]:
        """Return the world (x, z) coordinate of the highest-scoring cell."""
        scores           = self.analysis.scores
        idx              = np.argmax(scores)
        local_x, local_z = np.unravel_index(idx, scores.shape)
        wx, wz           = self.analysis.best_area.index_to_world(
            int(local_x), int(local_z)
        )
        return wx, wz