from __future__ import annotations

import numpy as np

from analysis.analyser import TerrainAnalyser
from analysis.fetcher import WorldFetcher
from analysis.patch_selector import PatchSelector
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from utils.interfaces import TerrainLoaderProtocol
from utils.terrain_utils import get_area_slice


class WorldAnalyser:
    """
    Analyses a Minecraft world build area and computes the best location
    for a settlement based on terrain, water, flatness, and biome scores.

    The best area is dynamically sized to fit the largest high-scoring patch.
    """

    def __init__(
        self,
        terrain_loader: TerrainLoaderProtocol,
        configuration: TerrainConfig,
    ) -> None:
        self.fetcher = WorldFetcher(terrain_loader)
        self.config  = configuration

    @staticmethod
    def _cap_area(area, max_size: int):
        """Return `area` shrunk to max_size × max_size centred on itself."""
        from data.build_area import BuildArea
        w, d = area.width, area.depth
        if w <= max_size and d <= max_size:
            return area
        cx = area.x_from + w // 2
        cz = area.z_from + d // 2
        half = max_size // 2
        return BuildArea(
            x_from=cx - half,  y_from=area.y_from,
            z_from=cz - half,  y_to=area.y_to,
            x_to=cx + half - 1, z_to=cz + half - 1,
        )

    def prepare(self) -> WorldAnalysisResult:
        """
        Fetch world data, analyse terrain metrics, and select the best patch.

        Returns
        -------
        WorldAnalysisResult
            Contains the selected build area and all terrain maps, each sliced
            to the best-patch extent.
        """
        # Fetch raw world data — cap to max_analysis_size to avoid timeouts
        # on very large build areas (e.g. competition-standard 1001×1001).
        build_area = self.fetcher.fetch_build_area()
        build_area = self._cap_area(build_area, self.config.max_analysis_size)
        surface, ground, ocean_floor, plant_thickness = (
            self.fetcher.fetch_heightmaps(build_area)
        )
        biomes = self.fetcher.fetch_biomes(build_area)

        # Analyse terrain across the full build area
        analyser = TerrainAnalyser(
            ground, surface, ocean_floor, biomes, self.config
        )
        analyser.compute_scores()

        # Select the best contiguous buildable patch (returns a sub-BuildArea)
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

        # Slice all full-area maps down to the best patch before surface scan.
        # Surface block fetching uses the sliced heightmap so its local x/z
        # indices align with best_area's world coordinates.
        def _slice(arr: np.ndarray) -> np.ndarray:
            return get_area_slice(build_area, best_area, arr)

        ground_sliced        = _slice(ground)
        surface_sliced       = _slice(surface)
        ocean_floor_sliced   = _slice(ocean_floor)
        plant_thickness_sliced = _slice(plant_thickness)

        # fetch_surface_block_ids must receive the already-sliced heightmap
        # so its chunk iteration stays within best_area's bounds.
        surface_blocks = self.fetcher.fetch_surface_block_ids(
            best_area, ground_sliced, self.config
        )

        return WorldAnalysisResult(
            best_area=best_area,
            surface_blocks=surface_blocks,
            heightmap_ground=      ground_sliced,
            heightmap_surface=     surface_sliced,
            heightmap_ocean_floor= ocean_floor_sliced,
            roughness_map=         _slice(analyser.roughness_map),
            plant_thickness=       plant_thickness_sliced,
            slope_map=             _slice(analyser.slope_map),
            water_mask=            _slice(analyser.water_mask),
            water_distances=       _slice(analyser.water_distances),
            biomes=                _slice(biomes),
            scores=                _slice(analyser.scores),
        )