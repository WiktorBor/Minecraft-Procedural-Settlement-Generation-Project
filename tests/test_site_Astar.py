import numpy as np
from utils.astar import find_path
from site_locator import SiteLocator
from data.build_area import BuildArea

# --- Mock World ---
class MockWorld:
    def __init__(self):
        self.heightmap_ground = np.ones((50,50), dtype=int) * 64
        self.slope_map = np.zeros((50,50))
        self.water_distances = np.full((50,50), 10)
        self.water_proximity = np.ones((50,50))
        self.build_area = BuildArea(0, 64, 0, 49, 70, 49)
        self.best_area = BuildArea(5, 64, 5, 44, 70, 44)

world = MockWorld()
editor = None  # Can be a mock editor if needed

# --- Site Locator Test ---
locator = SiteLocator(world, editor)
sites = locator.find_sites(max_sites=5)

assert len(sites) <= 5
for site in sites:
    a = site['area']
    assert world.best_area.contains_xz(a.x_from, a.z_from)

print("SiteLocator test passed with", len(sites), "sites found.")

# --- Pathway Test ---
def test_pathway_between_sites(site_locator, building_size=(7,7), path_width=1):
    sites = site_locator.sites
    if len(sites) < 2:
        print("Not enough sites to test paths.")
        return

    area = site_locator.settlement_area
    width, depth = area.width, area.depth
    walkable = np.ones((width, depth), dtype=bool)

    # Block site footprints with 1-block buffer
    for site in sites:
        sx = site['area'].x_from - area.x_from
        sz = site['area'].z_from - area.z_from
        for i in range(building_size[0]):
            for j in range(building_size[1]):
                x = sx + i
                z = sz + j
                if 1 <= x < width-1 and 1 <= z < depth-1:
                    walkable[x, z] = False

    # ASCII grid
    ascii_grid = np.full((width, depth), '.', dtype=str)

    # Mark sites
    for idx, site in enumerate(sites, 1):
        sx = site['area'].x_from - area.x_from
        sz = site['area'].z_from - area.z_from
        ascii_grid[sx:sx+building_size[0], sz:sz+building_size[1]] = str(idx)

    # Connect sites in order
    for idx in range(len(sites)-1):
        s0 = sites[idx]
        s1 = sites[idx+1]

        # Start/goal just outside the footprint
        start = (s0['area'].x_from - area.x_from + building_size[0], 
                 s0['area'].z_from - area.z_from + building_size[1]//2)
        goal = (s1['area'].x_from - area.x_from - 1, 
                s1['area'].z_from - area.z_from + building_size[1]//2)

        path = find_path(walkable, np.ones_like(walkable, dtype=int), start, goal)
        if path is None:
            print(f"No path between site {idx+1} and site {idx+2}")
            continue

        for x, z in path:
            if ascii_grid[x, z] == '.':
                ascii_grid[x, z] = '#'

    # Print ASCII map
    print("\nASCII map (sites as numbers, paths as #, empty = .):")
    for z in range(depth):
        row = "".join(ascii_grid[x, z] for x in range(width))
        print(row)

# --- Run Pathway Test ---
test_pathway_between_sites(locator)