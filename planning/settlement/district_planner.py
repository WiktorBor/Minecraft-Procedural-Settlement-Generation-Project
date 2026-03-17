import numpy as np
from scipy.spatial import Voronoi
import random

from data.configurations import SettlementConfig
from data.settlement_entities import Districts, District
from utils.poisson_disk import poisson_disk
from data.analysis_results import WorldAnalysisResult

class DistrictPlanner:
    """
    Voronoi-based district planner.
    Generates districts and assigns types based on terrain features.
    """

    def __init__(
            self, 
            analysis: WorldAnalysisResult, 
            config: SettlementConfig, 
            num_districts=None, 
            seed=None
    ):
        self.analysis = analysis
        self.config = config
        self.num_districts = num_districts or self.config.num_districts
        self.seed = seed

        if self.seed is not None:
            random.seed(self.seed)
            np.random.seed(self.seed)

    def generate(self) -> Districts:
        """
        Generate districts within the best build area.
        
        Returns:
            Districts: map, types, seeds, Voronoi object, district list
        """
        area = self.analysis.best_area
        print("  Generating districts...")

        local_slope = self.analysis.slope_map
        local_roughness = self.analysis.roughness_map
        local_water_distances = self.analysis.water_distances

        w, d = local_slope.shape

        max_slope = max(local_slope.max(), 1e-5)
        max_rough = max(local_roughness.max(), 1e-5)
    
        # Create a score map for district seed placement
        score = np.clip(
            1
            - 0.5 * (local_slope / max_slope)
            - 0.3 * (local_roughness / max_rough),
            0, 1
        )

        score = np.clip(score, 0, 1)
 
        # Generate Voronoi seeds
        seeds = poisson_disk(
            width=w,
            height=d,
            radius=max(self.config.radius, min(w, d) / (self.num_districts * 2)),
            score_map=score,
            seed=self.seed
        )

        # Limit seeds to num_districts if we got more than needed
        if len(seeds) > self.num_districts:
            indices = np.random.choice(len(seeds), size=self.num_districts, replace=False)
            seeds = seeds[indices]

        vor = Voronoi(seeds)

        # Vectorized Voronoi map
        xs, zs = np.meshgrid(np.arange(w), np.arange(d), indexing='ij')
        grid = np.stack((xs, zs), axis=-1)
        distances = np.sum((grid[..., None, :] - seeds) ** 2, axis=-1)
        district_map: np.ndarray = np.argmin(distances, axis=-1)

        # Flatten arrays for aggregation
        district_ids = district_map.ravel()
        slope_flat = local_slope.ravel()
        roughness_flat = local_roughness.ravel()
        water_dist_flat = local_water_distances.ravel()
        xs_flat = xs.ravel()
        zs_flat = zs.ravel()

        # Compute counts and averages
        counts = np.bincount(district_ids, minlength=self.num_districts)
        counts = np.maximum(counts, 1)  # Avoid division by zero
        avg_slope = np.bincount(district_ids, weights=slope_flat,minlength=self.num_districts) / counts
        avg_roughness = np.bincount(district_ids, weights=roughness_flat, minlength=self.num_districts) / counts
        avg_water_dist = np.bincount(district_ids, weights=water_dist_flat, minlength=self.num_districts) / counts

        # Compute bounding boxes
        x_min = np.full(self.num_districts, np.inf)
        z_min = np.full(self.num_districts, np.inf)
        x_max = np.full(self.num_districts, -np.inf)
        z_max = np.full(self.num_districts, -np.inf)

        np.minimum.at(x_min, district_ids, xs_flat)
        np.minimum.at(z_min, district_ids, zs_flat)
        np.maximum.at(x_max, district_ids, xs_flat)
        np.maximum.at(z_max, district_ids, zs_flat)

        # Assign district types and build District objects
        district_types = {}
        district_list = []

        for idx in range(self.num_districts):

            slope = avg_slope[idx]
            roughness = avg_roughness[idx]
            water_dist = avg_water_dist[idx]

            # Simple heuristic for district type
            dtype = "forest" # default fallback
            for candidate_type, rules in self.config.district_type_rules.items():
                if candidate_type == "fishing":
                    if water_dist <= rules.get("water_dist_max", np.inf):
                        dtype = "fishing"
                        break

                elif candidate_type in ["farming", "residential"]:
                    slope_ok = slope <= rules.get("slope_max", np.inf)
                    rough_ok = roughness <= rules.get("roughness_max", np.inf)
                    
                    if slope_ok and rough_ok:
                        dtype = candidate_type if random.random() < rules.get("probability", 0.5) else "residential"
                        break

            district_types[idx] = dtype

            xmin = int(x_min[idx])
            xmax = int(x_max[idx])
            zmin = int(z_min[idx])
            zmax = int(z_max[idx])
            wx, wz = area.index_to_world(xmin, zmin)

            # Compute district center in local indices -> world
            cells = np.argwhere(district_map == idx)
            x_center = int(np.mean(cells[:,0]))
            z_center = int(np.mean(cells[:,1]))
            cx, cz = area.index_to_world(x_center, z_center)

            width = xmax - xmin + 1
            depth = zmax - zmin + 1

            district_list.append(
                District(
                    x=wx,
                    z=wz,
                    width=width,
                    depth=depth,
                    center=(cx, cz),
                    type=dtype
                )
            )

        return Districts(
            map=district_map,
            types=district_types,
            seeds=vor.points,
            voronoi=vor,
            district_list=district_list
        )