class DistrictPlanner:

    def __init__(self, analysis, state):
        self.analysis = analysis
        self.state = state

    def generate(self):

        print("  Generating districts...")

        best_area = self.analysis.best_area

        # For now we create a single village district
        self.state.districts = {
            "village": best_area
        }