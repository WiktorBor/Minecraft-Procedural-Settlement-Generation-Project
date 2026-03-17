from .infrastructure.road_planner import RoadPlanner
from .settlement.plot_planner import PlotPlanner
from .settlement.district_planner import DistrictPlanner
from data.settlement_state import SettlementState
from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig

import numpy as np

class SettlementPlanner:
    """
    Main planner that orchestrates district, plot, and road generation.
    """

    def __init__(
            self, 
            analysis: WorldAnalysisResult, 
            config: SettlementConfig
    ):
        self.analysis = analysis
        self.config = config

    def plan(self) -> SettlementState:
        """
        Main planning function: generates districts, plots, and roads.

        Returns:
            SettlementState: updated state with planned districts, plots, and roads.
        """
        state = SettlementState()

        # Choose settlement center based on analysis scores
        state.center = self._choose_center()

        # Generate districts
        district_planner = DistrictPlanner(
            analysis=self.analysis,
            config=self.config
        )

        districts = district_planner.generate()
        state.districts = districts

        # Generate roads
        road_planner = RoadPlanner(
            analysis=self.analysis,
            districts=districts,
            config=self.config
        )

        roads = road_planner.generate()
        state.roads = roads

        # Generate plots
        plot_planner = PlotPlanner(
            analysis=self.analysis,
            districts=districts,
            roads=roads,
            config=self.config
        )
        plots = plot_planner.generate()
        state.plots = plots

        return state

# ___________________________________________________________________
# Might be useful for future improvements
#____________________________________________________________________
    def _choose_center(self):
        scores = self.analysis.scores

        idx = np.argmax(scores)
        cx, cz = np.unravel_index(idx, scores.shape)

        cx += self.analysis.best_area.x_from
        cz += self.analysis.best_area.z_from
        
        return (cx, cz)
