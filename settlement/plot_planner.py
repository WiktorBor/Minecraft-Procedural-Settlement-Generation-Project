import random
import math

class PlotPlanner:

    def __init__(self, analysis, state, config):
        self.analysis = analysis
        self.state = state
        self.config = config

    def generate(self):

        print("  Generating plots (Poisson disk)...")

        area = self.analysis.best_area
        min_dist = self.config.min_plot_distance

        samples = self._poisson_disk(area.width, area.depth, min_dist)

        plots = []

        for sx, sz in samples:

            # convert local → world
            x = int(area.x_from + sx)
            z = int(area.z_from + sz)

            if self._valid(x, z):
                plots.append((x, z))

        self.state.plots = plots


    def _poisson_disk(self, width, height, radius, k=30):

        cell_size = radius / math.sqrt(2)

        grid_w = int(width / cell_size) + 1
        grid_h = int(height / cell_size) + 1

        grid = [[None for _ in range(grid_h)] for _ in range(grid_w)]

        samples = []
        active = []

        # first sample
        x = random.uniform(0, width)
        z = random.uniform(0, height)

        samples.append((x, z))
        active.append((x, z))

        gx = int(x / cell_size)
        gz = int(z / cell_size)

        grid[gx][gz] = (x, z)

        while active:

            idx = random.randrange(len(active))
            px, pz = active[idx]

            found = False

            for _ in range(k):

                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(radius, 2 * radius)

                x = px + math.cos(angle) * dist
                z = pz + math.sin(angle) * dist

                if not (0 <= x < width and 0 <= z < height):
                    continue

                gx = int(x / cell_size)
                gz = int(z / cell_size)

                ok = True

                for ix in range(max(gx - 2, 0), min(gx + 3, grid_w)):
                    for iz in range(max(gz - 2, 0), min(gz + 3, grid_h)):

                        neighbor = grid[ix][iz]

                        if neighbor is None:
                            continue

                        dx = neighbor[0] - x
                        dz = neighbor[1] - z

                        if dx * dx + dz * dz < radius * radius:
                            ok = False
                            break

                    if not ok:
                        break

                if ok:

                    samples.append((x, z))
                    active.append((x, z))
                    grid[gx][gz] = (x, z)

                    found = True
                    break

            if not found:
                active.pop(idx)

        return samples


    def _valid(self, x, z):

        area = self.analysis.best_area

        if not (area.x_from <= x < area.x_to and
                area.z_from <= z < area.z_to):
            return False

        bx = area.x_from
        bz = area.z_from

        gx = x - bx
        gz = z - bz

        if self.analysis.slope_map[gx, gz] > self.config.max_slope:
            return False

        if self.analysis.roughness_map[gx, gz] > self.config.max_roughness:
            return False

        if self.analysis.water_distances[gx, gz] < self.config.min_water_distance:
            return False

        return True