from settlement.road_planner import RoadPlanner
from settlement.plot_planner import PlotPlanner
from settlement.district_planner import DistrictPlanner

import numpy as np
class SettlementPlanner:

    def __init__(self, analysis, state, config):
        self.analysis = analysis
        self.state = state
        self.config = config

    def plan(self):

        print("Planning settlement...")
        self._choose_center()

        district_planner = DistrictPlanner(
            self.analysis, self.state
        )
        district_planner.generate()

        plot_planner = PlotPlanner(
            self.analysis, self.state, self.config
        )
        plot_planner.generate()

        road_planner = RoadPlanner(
            self.analysis, self.state
        )
        road_planner.generate()

        return self.state
    
    def _choose_center(self):
        scores = self.analysis.scores

        idx = np.argmax(scores)
        cx, cz = np.unravel_index(idx, scores.shape)

        cx += self.analysis.build_area.x_from
        cz += self.analysis.build_area.z_from
        
        self.state.center = (cx, cz)


# class SettlementPlanner:

#     def __init__(self, analysis, state, config):
#         self.analysis = analysis
#         self.state = state
#         self.config = config

#     def plan(self):
#         self._choose_center()

#         district_planner = DistrictPlanner(self.analysis, self.state)
#         district_planner.generate()

#         road_planner = RoadPlanner(self.analysis, self.state)
#         road_planner.generate()

#         plot_planner = PlotPlanner(self.analysis, self.state, self.config)
#         plot_planner.generate()

#         return self.state
