from data.settlement_entities import RoadCell

class RoadPlanner:

    def __init__(self, analysis, state):
        self.analysis = analysis
        self.state = state

    def generate(self):

        print("  Generating roads...")

        cx, cz = self.state.center
        area = self.analysis.best_area

        roads = set()

        for x in range(area.x_from, area.x_to + 1):
            roads.add(RoadCell(x, cz))

        for z in range(area.z_from, area.z_to + 1):
            roads.add(RoadCell(cx, z))

        self.state.roads = list(roads)