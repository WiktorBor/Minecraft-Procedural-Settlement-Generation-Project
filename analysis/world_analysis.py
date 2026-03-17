from .fetcher import WorldFetcher
from .analyser import TerrainAnalyser
from .patch_selector import PatchSelector
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from world_interface.terrain_loader import TerrainLoader
from utils.terrain_utils import get_area_slices

class WorldAnalyser:
    """
    Analyse a Minecraft world build area and compute the best location
    for building a settlement based on terrain, water, flatness and biome.
    The best area is dinamically sized to fit the largest high-scoring patch."""
    def __init__(self, terrain_loader: TerrainLoader, configuration: TerrainConfig):
        self.fetcher = WorldFetcher(terrain_loader)
        self.config = configuration

    def prepare(self) -> WorldAnalysisResult:
        """
        Fetch world data, analyse terrain metrics and select the best patch.
        
        Returns:
            WorldAnalysisResult: contains build area, best area and all terrain maps.
        """

        # Fetch raw data
        build_area = self.fetcher.fetch_build_area()
        surface, ground, ocean_floor, plant_thickness = self.fetcher.fetch_heightmaps(build_area)
        biomes = self.fetcher.fetch_biomes(build_area)

        # Analyse terrain
        analyser = TerrainAnalyser(ground, surface, ocean_floor, biomes, self.config)
        analyser.compute_scores()

        # Select best buildable patch
        selector = PatchSelector(
            build_area=build_area,
            scores=analyser.scores,
            slope_map=analyser.slope_map,
            water_mask=analyser.water_mask,
            roughness_map=analyser.roughness_map, 
            heightmap_ground=ground,
            config=self.config
        )

        best_area = selector.select_best_patch()
        surface = get_area_slices(build_area, best_area, surface)
        ground = get_area_slices(build_area, best_area, ground)
        ocean_floor = get_area_slices(build_area, best_area, ocean_floor)
        plant_thickness = get_area_slices(build_area, best_area, plant_thickness)
        slope_map = get_area_slices(build_area, best_area, analyser.slope_map)
        water_mask = get_area_slices(build_area, best_area, analyser.water_mask)
        roughness_map = get_area_slices(build_area, best_area, analyser.roughness_map)
        scores = get_area_slices(build_area, best_area, analyser.scores)
        water_distances = get_area_slices(build_area, best_area, analyser.water_distances)
        biomes = get_area_slices(build_area, best_area, biomes)

        return WorldAnalysisResult(
            best_area=best_area,
            heightmap_ground=ground,
            heightmap_surface=surface,
            heightmap_ocean_floor=ocean_floor,
            roughness_map=roughness_map,
            plant_thickness=plant_thickness,
            slope_map=slope_map,
            water_mask=water_mask,
            water_distances=water_distances,
            biomes=biomes,
            scores=scores
        )
