import numpy as np
from data.build_area import BuildArea
from planning.settlement.district_planner import DistrictPlanner
from data.settlement_state import SettlementState
from planning.infrastructure.road_planner import RoadPlanner
from data.configurations import SettlementConfig

# ----------------- MOCK WORLD -----------------
class MockWorld:
    def __init__(self):
        # Full build area
        self.build_area = BuildArea(0, 64, 0, 59, 70, 59)

        # Best settlement area (from 10→50, so width=41, depth=41)
        self.best_area = BuildArea(10, 64, 10, 50, 70, 50)

        # Heightmap / slope / roughness / biomes / water distances all need to cover full build_area
        self.heightmap_ground = np.ones((60, 60)) * 64
        self.slope_map = np.zeros((60, 60))
        self.roughness_map = np.zeros((60, 60))
        self.water_distances = np.full((60, 60), 10)
        self.water_proximity = np.ones((60, 60))
        self.biomes = np.full((60, 60), "plains")

world = MockWorld()
state = SettlementState()
config=SettlementConfig

# ----------------- DISTRICTS + PLOTS -----------------
planner = DistrictPlanner(world, config, num_districts=4, seed=42)
districts = planner.generate()

roads = RoadPlanner(world, districts)
roads.generate()

# ----------------- ASCII VISUALIZATION -----------------
# Assuming best_area from analysis
width, depth = world.best_area.width, world.best_area.depth
ascii_grid = np.full((width, depth), '.', dtype=str)

# Draw districts (using district_types as labels)
district_map = districts.get("map")
for i in range(width):
    for j in range(depth):
        d = district_map[i, j]
        ascii_grid[i, j] = str(d % 10)  # single-digit label

# Print ASCII map
for j in range(depth):
    row = "".join(ascii_grid[i, j] for i in range(width))
    print(row)
