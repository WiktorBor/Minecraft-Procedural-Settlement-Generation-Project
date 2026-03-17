import numpy as np
from data.build_area import BuildArea
from site_locator import SiteLocator
from pathfinding.pathway_builder import build_walkable_grid 
from data.build_area import BuildArea

# --- Mock World / Editor ---
class MockWorld:
    def __init__(self):
        self.heightmap_ground = np.ones((50, 50)) * 64   # flat ground at y=64
        self.slope_map = np.zeros((50, 50))
        self.water_distances = np.full((50, 50), 10)
        self.water_proximity = np.ones((50, 50))
        self.build_area = BuildArea(0, 64, 0, 49, 64, 49)
        self.best_area = BuildArea(5, 64, 5, 44, 70, 44)

class MockEditor:
    def placeBlock(self, pos, block):
        print(f"Placing block {block} at {pos}")
    def flushBuffer(self):
        print("Flushed buffer.")

# --- Setup SiteLocator ---
world = MockWorld()
editor = MockEditor()
site_locator = SiteLocator(world, editor)

# Find sites
sites = site_locator.find_sites(
    max_sites=5,
    building_size=(7, 7),
    min_gap=4
)
site_locator.visualize_sites()

# --- Build a walkable grid ---
walkable = build_walkable_grid(world, [
    {"position": (site['area'].x_from, site['area'].y_from, site['area'].z_from),
     "size": (7, 7, 7)}
    for site in sites
])

print("Walkable grid (1=walkable, 0=blocked):")
print(walkable.astype(int))

# --- Check site to site connections (mock path) ---
for i in range(len(sites)-1):
    a = sites[i]['area']
    b = sites[i+1]['area']
    a_local = world.best_area.world_to_index(a.x_from, a.z_from)
    b_local = world.best_area.world_to_index(b.x_from, b.z_from)
    print(f"Path from site {i+1} at {a_local} to site {i+2} at {b_local}")