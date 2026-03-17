from typing import List, Set, Tuple
import numpy as np
from utils.poisson_disk import poisson_disk
from data.settlement_entities import Plot, Districts, RoadCell
from data.analysis_results import WorldAnalysisResult
from data.configurations import SettlementConfig

class PlotPlanner:
    """
    Creates building plots within each district,
      ensuring they fit terrain constraints and do not overlap with roads or other plots.
    """

    def __init__(
            self, 
            analysis: WorldAnalysisResult, 
            districts: Districts,
            roads: List[RoadCell],
            config: SettlementConfig
    ):
        self.analysis = analysis
        self.districts = districts
        self.road_set: Set[Tuple[int, int]] = {(r.x, r.z) for r in roads}
        self.config = config

    def _valid(
            self, 
            x_start: int, 
            z_start: int, 
            plot_w: int, 
            plot_d: int
    ) -> bool:
        """
        Validate that the entire plot rectangle is on suitable terrain.
        """
        area = self.analysis.best_area

        heights = []

        for dx in range(plot_w):
            for dz in range(plot_d):

                x = x_start + dx
                z = z_start + dz

                if not area.contains_xz(x, z):
                    return False

                ix, iz = area.world_to_index(x, z)

                if self.analysis.slope_map[ix, iz] > self.config.max_slope:
                    return False

                if self.analysis.roughness_map[ix, iz] > self.config.max_roughness:
                    return False

                if self.analysis.water_distances[ix, iz] < self.config.min_water_distance:
                    return False

                if (x, z) in self.road_set:
                    return False
                
                heights.append(self.analysis.heightmap_ground[ix, iz])

        if max(heights) - min(heights) > self.config.max_height_variation:
            return False
        
        return True
    
    def _center_distance(self, x1, z1, x2, z2):
        return np.sqrt((x1-x2)**2 + (z1-z2)**2)
    
    def _road_direction(self, x, z):

        neighbors = [
            (x+1, z),
            (x-1, z),
            (x, z+1),
            (x, z-1)
        ]

        for nx, nz in neighbors:
            if (nx, nz) in self.road_set:
                return nx-x, nz-z

        return None

    def generate(self) -> List[Plot]:
        """
        Generate plots inside each Voronoi district, 
        respecting terrain constraints and avoiding overlaps.
        """
        districts_map = self.districts.map
        districts_types = self.districts.types

        w, d = districts_map.shape
        occupied = np.zeros((w, d), dtype=bool)

        plots: List[Plot] = []
        plot_centers: List[Tuple[int, int]] = []

        for district_idx, dtype in districts_types.items():
            district_mask = districts_map == district_idx

            if not np.any(district_mask):
                continue

            # Determine Poisson radius / spacing
            min_dist = self.config.min_plot_distance

            if dtype == "residential":
                min_dist = max(2, min_dist // 2)
            elif dtype == "farming":
                min_dist = int(min_dist * 1.5)
            elif dtype == "fishing":
                min_dist = min_dist
            else:
                min_dist = int(min_dist * 2)

            # Get bounding box of the district
            xs, zs = np.where(district_mask)

            x_min, x_max = xs.min(), xs.max()
            z_min, z_max = zs.min(), zs.max()

            # Sample points in the bounding rectangle
            width = x_max - x_min + 1 
            depth = z_max - z_min + 1

            sample_points = poisson_disk(
                width=width, 
                height=depth, 
                radius=min_dist
            )

            for lx, lz in sample_points:
                local_x = int(x_min + lx)
                local_z = int(z_min + lz)

                if local_x >=w or local_z >= d:
                    continue

                # Plot size from config
                plot_w = self.config.plot_width.get(dtype, 8)
                plot_d = self.config.plot_depth.get(dtype, 8)

                min_size = self.config.min_plot_size.get(dtype, 4)

                if plot_w < min_size or plot_d < min_size:
                    continue

                occ_slice = occupied[
                    local_x:local_x + plot_w,
                    local_z:local_z + plot_d
                ]

                dist_slice = district_mask[
                    local_x:local_x + plot_w,
                    local_z:local_z + plot_d
                ]

                if occ_slice.shape != (plot_w, plot_d):
                    continue

                if np.any(occ_slice | ~dist_slice):
                    continue

                # Convert to world coordinates
                wx, wz = self.analysis.best_area.index_to_world(local_x, local_z)

                if not self._valid(wx, wz, plot_w, plot_d):
                    continue

                if plot_centers:
                    cx = local_x + plot_w // 2
                    cz = local_z + plot_d // 2

                    distances = [
                        self._center_distance(
                            cx, cz, px, pz)
                        for px, pz in plot_centers
                    ]
                    nearest = min(distances)

                    if nearest < self.config.min_plot_cluster_distance:
                        continue

                    if nearest > self.config.max_plot_cluster_distance:
                        if np.random.random() < 0.6:
                            continue
                block_radius = self.config.min_plot_cluster_distance // 2
                
                # Mark the **entire plot area** as occupied
                occupied[
                    max(0, local_x - block_radius):min(w, local_x + plot_w + block_radius), 
                    max(0, local_z - block_radius):min(d, local_z + plot_d + block_radius)
                ] = True

                cx = local_x + plot_w // 2
                cz = local_z + plot_d // 2

                plot_centers.append((cx, cz))

                plots.append(
                    Plot(
                        x=wx,
                        y=self.analysis.heightmap_ground[local_x, local_z],
                        z=wz,
                        width=plot_w,
                        depth=plot_d,
                        type=dtype
                    )
                )

        return plots