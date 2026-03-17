"""SettlementGenerator for current pipeline: builds districts, plots, and structures (houses only)."""

from planning.settlement_planner import SettlementPlanner
from structures.house.house import House  # currently only house; extendable later


class SettlementGenerator:

    def __init__(self, editor, analyser, config):
        self.editor = editor
        self.analyser = analyser      # WorldAnalysisResult
        self.config = config          # SettlementConfig
        self.planner = SettlementPlanner(analyser, config)

    def generate(self, num_buildings=None):
        """
        Generate complete settlement:
            - Plan districts, roads, plots
            - Build structures (houses) on plots
        """
        print("\n" + "="*50)
        print("SETTLEMENT GENERATOR")
        print("="*50)

        # 1️⃣ Settlement planning: districts, roads, plots
        print("\n[Phase 1] Settlement Planning...")
        self.state = self.planner.plan()
        print(f"  ✓ {len(self.state.districts.district_list)} districts, "
              f"{len(self.state.roads)} road cells, {len(self.state.plots)} plots ready")

        # 2️⃣ Build structures (houses) on plots
        print("\n[Phase 2] Structure Generation...")
        plots_to_build = self.state.plots
        if num_buildings is not None:
            plots_to_build = plots_to_build[:num_buildings]

        for idx, plot in enumerate(plots_to_build, 1):
            house = House(self.editor, self.analyser)
            print(f"  Building {idx}/{len(plots_to_build)} at plot ({plot.x}, {plot.z})")
            house.build(plot)
            # Store metadata in state.buildings
            building_data = {
                "type": "house",
                "plot": plot
            }
            self.state.buildings.append(building_data)

        print(f"  ✓ Generated {len(self.state.buildings)} buildings")

        # 3️⃣ Finalize
        self._finalize()

    # ----------------------------
    # Private helpers
    # ----------------------------
    def _finalize(self):
        print("\n[Phase 3] Finalizing...")
        print("  Flushing blocks to Minecraft...")
        self.editor.flushBuffer()
        print("  ✓ All blocks placed!")