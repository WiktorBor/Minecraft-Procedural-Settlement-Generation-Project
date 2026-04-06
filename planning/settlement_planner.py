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
    Orchestrates district, road, and plot generation to produce a SettlementState.

    Each method receives analysis as an argument so the planner can be
    constructed before world analysis has run.
    """

    def __init__(self, config: SettlementConfig) -> None:
        self.config = config

    def plan_districts(self, analysis: WorldAnalysisResult) -> SettlementState:
        """
        Choose settlement centre and generate Voronoi districts.

        Returns a SettlementState with centre and districts populated.
        Roads and plots are empty — register fountain cells into state.occupancy,
        then call plan_roads(analysis, state).
        """
        state        = SettlementState()
        state.center = self._choose_center(analysis)
        logger.info("Settlement centre: %s", state.center)

        area         = analysis.best_area
        w, d         = area.width, area.depth
        plaza_radius = min(min(w, d) // 10, 15)
        if plaza_radius < 3:
            plaza_radius = 0

        if plaza_radius > 0:
            cx_w = (area.x_from + area.x_to) // 2
            cz_w = (area.z_from + area.z_to) // 2
            state.plaza_center = (cx_w, cz_w)
            state.plaza_radius = plaza_radius

            road_width  = self.config.road_width
            excl_radius = plaza_radius + road_width + 1 + road_width // 2
            excl_center = (w // 2, d // 2)
        else:
            excl_center = None
            excl_radius = 0

        logger.info("Planning districts...")
        district_planner = DistrictPlanner(
            analysis=analysis,
            config=self.config,
            exclusion_center=excl_center,
            exclusion_radius=excl_radius,
        )
        state.districts = district_planner.generate()
        logger.info("Generated %d districts.", len(state.districts.district_list))

        return state

    def plan_roads(self, analysis: WorldAnalysisResult, state: SettlementState) -> None:
        """
        Generate roads connecting district centres. Mutates state in-place.

        Call after plan_districts() and after fountains have been registered
        into state.occupancy.
        """
        logger.info("Planning roads...")
        hub = (
            (float(state.plaza_center[0]), float(state.plaza_center[1]))
            if state.plaza_center is not None
            else None
        )
        road_planner = RoadPlanner(
            analysis=analysis,
            districts=state.districts,
            config=self.config,
            hub_point=hub,
        )
        roads = road_planner.generate()
        state.add_road_cells(roads)
        logger.info("Generated %d road cells.", state.road_cell_count)

    def plan_plots(self, analysis: WorldAnalysisResult, state: SettlementState) -> None:
        """
        Generate building plots validated against all taken tiles. Mutates state in-place.

        Call after plan_roads() so state.occupancy contains fountain and road footprints.
        """
        logger.info("Planning plots...")
        plot_planner = PlotPlanner(
            analysis=analysis,
            districts=state.districts,
            occupancy=state.occupancy,
            config=self.config,
            road_coords=state._road_coords,
        )
        for plot in plot_planner.generate():
            state.add_plot(plot)
        logger.info("Generated %d plots.", state.plot_count)

    def _choose_center(self, analysis: WorldAnalysisResult) -> tuple[int, int]:
        """Return the world (x, z) coordinate of the highest-scoring cell."""
        scores           = analysis.scores
        idx              = np.argmax(scores)
        local_x, local_z = np.unravel_index(idx, scores.shape)
        wx, wz           = analysis.best_area.index_to_world(int(local_x), int(local_z))
        return wx, wz
