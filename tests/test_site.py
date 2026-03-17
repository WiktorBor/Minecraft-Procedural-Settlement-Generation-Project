import numpy as np
from data.build_area import BuildArea
from site_locator import SiteLocator

# Mock world
class MockWorld:
    def __init__(self):
        self.heightmap_ground = np.ones((50,50)) * 64
        self.slope_map = np.zeros((50,50))
        self.water_distances = np.full((50,50), 10)
        self.water_proximity = np.ones((50,50))
        self.build_area = BuildArea(0, 64, 0, 49, 70, 49)
        self.best_area = BuildArea(5, 64, 5, 44, 70, 44)

world = MockWorld()
editor = None  # Or mock editor that just records blocks placed

locator = SiteLocator(world, editor)
sites = locator.find_sites(max_sites=5)

assert len(sites) <= 5
for site in sites:
    a = site['area']
    assert world.best_area.contains_xz(a.x_from, a.z_from)


print("SiteLocator test passed with", len(sites), "sites found.")