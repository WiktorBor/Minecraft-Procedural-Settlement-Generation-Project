from analysis.world_analysis import WorldAnalyser
from world_interface.terrain_loader import TerrainLoader
from utils.http_client import GDMCClient
from data.build_area import BuildArea
import numpy as np

client = GDMCClient()
terrain = TerrainLoader(client)  # Pass None or a mock client if needed
world = WorldAnalyser(terrain)# Pass None or a mock TerrainLoader if needed
# Example check inside WorldAnalyser or a test script
raw_build_area = terrain.get_build_area()  # dict
build_area = BuildArea(
    x_from = raw_build_area["xFrom"],
    y_from = raw_build_area["yFrom"],
    z_from = raw_build_area["zFrom"],
    x_to   = raw_build_area["xTo"],
    y_to   = raw_build_area["yTo"],
    z_to   = raw_build_area["zTo"],
)

# Fetch a small heightmap slice (e.g., 5x5)
x_from, z_from = build_area.x_from, build_area.z_from
width, depth = 5, 5

heightmap = world.terrain.get_heightmap(x_from, z_from, width, depth, "MOTION_BLOCKING")

print("Heightmap shape:", np.array(heightmap).shape)
print("Heightmap values:")
for i, row in enumerate(heightmap):
    print(f"x={x_from + i}:", row)