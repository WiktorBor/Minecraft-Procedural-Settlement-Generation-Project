from __future__ import annotations

import logging

import numpy as np

from .infrastructure.road_planner import RoadPlanner
from .settlement.district_planner import DistrictPlanner
from .settlement.plot_planner import PlotPlanner
from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig
from data.settlement_state import SettlementState

logger = logging.getLogger(__name__)


class SettlementPlanner:
    """
    Orchestrates district, plot, and road generation to produce a SettlementState.

    Pipeline
    --------
    1. plan_districts()  — choose centre, generate Voronoi districts.
    2. (caller runs terrain cleanup here, districts now known)
    3. plan_roads_and_plots()  — road network + building plots.

    Use plan() to run the full pipeline in one call, or call the two
    sub-methods separately to insert terrain cleanup in between.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        config: SettlementConfig,
    ) -> None:
        self.analysis = analysis
        self.config   = config

    # ------------------------------------------------------------------
    # Full pipeline (convenience wrapper)
    # ------------------------------------------------------------------

    def plan(self) -> SettlementState:
        """Run the full planning pipeline without any mid-step intervention."""
        state = self.plan_districts()
        self.plan_roads_and_plots(state)
        return state

    # ------------------------------------------------------------------
    # Split pipeline — use these when terrain cleanup runs in between
    # ------------------------------------------------------------------

    def plan_districts(self) -> SettlementState:
        """
        Phase 1: choose settlement centre and generate Voronoi districts.

        Returns a SettlementState with centre and districts populated.
        Roads and plots are empty — call plan_roads_and_plots() next.
        """
        state = SettlementState()

        state.center = self._choose_center()
        logger.info("Settlement centre: %s", state.center)

        logger.info("Planning districts...")
        district_planner = DistrictPlanner(
            analysis=self.analysis,
            config=self.config,
        )
        state.districts = district_planner.generate()
        logger.info("Generated %d districts.", len(state.districts.district_list))

        return state

    def plan_roads_and_plots(self, state: SettlementState) -> None:
        """
        Phase 2: generate roads and plots into an existing SettlementState.

        Call this after plan_districts() — and after any terrain cleanup that
        should see the updated heightmap before road/plot placement.

        Mutates `state` in-place (adds road cells and plots).
        """
        # Roads
        logger.info("Planning roads...")
        road_planner = RoadPlanner(
            analysis=self.analysis,
            districts=state.districts,
            config=self.config,
        )
        roads = road_planner.generate()
        state.add_road_cells(roads)
        logger.info("Generated %d road cells.", state.road_cell_count)

        # Plots
        logger.info("Planning plots...")
        plot_planner = PlotPlanner(
            analysis=self.analysis,
            districts=state.districts,
            roads=state.roads,
            config=self.config,
        )
        for plot in plot_planner.generate():
            state.add_plot(plot)
        logger.info("Generated %d plots.", state.plot_count)

    def _choose_center(self) -> tuple[int, int]:
        """Return the world (x, z) coordinate of the highest-scoring cell."""
        scores           = self.analysis.scores
        idx              = np.argmax(scores)
        local_x, local_z = np.unravel_index(idx, scores.shape)
        wx, wz           = self.analysis.best_area.index_to_world(int(local_x), int(local_z))
        return wx, wz