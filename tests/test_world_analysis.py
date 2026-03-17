from analysis.world_analysis import WorldAnalyser
from world_interface.terrain_loader import TerrainLoader
from utils.http_client import GDMCClient
from data.configurations import TerrainConfig
import numpy as np

# Initialize client and terrain loader
client = GDMCClient()
terrain = TerrainLoader(client)

# Initialize config
config = TerrainConfig()

# Initialize WorldAnalyser orchestrator
world_analyser = WorldAnalyser(terrain, config)

# Run full analysis and get results
result = world_analyser.prepare()

# Access results
print("Best Build Area:", result.best_area)
print("Slope map shape:", result.slope_map.shape)
print("Width, depth:", result.best_area.width, result.best_area.depth)
print("Heightmap shape:", result.heightmap_ground.shape)
print("Scores shape:", result.scores.shape)

# Example: print a small slice of the heightmap
x_slice, z_slice = slice(0, 5), slice(0, 5)
print("Heightmap slice (ground):")
print(result.heightmap_ground[x_slice, z_slice])

print("Scores slice:")
print(result.scores[x_slice, z_slice])