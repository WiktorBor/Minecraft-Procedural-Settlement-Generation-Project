from __future__ import annotations

import numpy as np
from .fetcher import WorldFetcher
from .analyser import TerrainAnalyser
from .patch_selector import PatchSelector
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from world_interface.terrain_loader import TerrainLoader
from utils.terrain_utils import get_area_slices


class WorldAnalyser:
    """
    Analyses a Minecraft world build area and computes the best location
    for a settlement based on terrain, water, flatness, and biome scores.

    The best area is dynamically sized to fit the largest high-scoring patch.
    """

    def __init__(self, terrain_loader: TerrainLoader, configuration: TerrainConfig) -> None:
        self.fetcher = WorldFetcher(terrain_loader)
        self.config  = configuration

    def prepare(self) -> WorldAnalysisResult:
        """
        Fetch world data, analyse terrain metrics, and select the best patch.

        Returns
        -------
        WorldAnalysisResult
            Contains the selected build area and all terrain maps, sliced to
            the best patch extent.
        """
        # --- fetch raw world data ---
        build_area = self.fetcher.fetch_build_area()
        surface, ground, ocean_floor, plant_thickness = self.fetcher.fetch_heightmaps(build_area)
        biomes = self.fetcher.fetch_biomes(build_area)

        # --- analyse terrain ---
        analyser = TerrainAnalyser(ground, surface, ocean_floor, biomes, self.config)
        analyser.compute_scores()

        # --- select best buildable patch ---
        selector = PatchSelector(
            build_area=build_area,
            scores=analyser.scores,
            slope_map=analyser.slope_map,
            water_mask=analyser.water_mask,
            roughness_map=analyser.roughness_map,
            heightmap_ground=ground,
            config=self.config,
        )
        best_area = selector.select_best_patch()

        # --- slice all maps to the best area ---
        def _slice(arr: np.ndarray) -> np.ndarray:
            return get_area_slices(build_area, best_area, arr)

        return WorldAnalysisResult(
            best_area=best_area,
            heightmap_ground=      _slice(ground),
            heightmap_surface=     _slice(surface),
            heightmap_ocean_floor= _slice(ocean_floor),
            roughness_map=         _slice(analyser.roughness_map),
            plant_thickness=       _slice(plant_thickness),
            slope_map=             _slice(analyser.slope_map),
            water_mask=            _slice(analyser.water_mask),
            water_distances=       _slice(analyser.water_distances),
            biomes=                _slice(biomes),
            scores=                _slice(analyser.scores),
        )