"""SettlementGenerator — builds districts, plots, roads, and structures."""
from __future__ import annotations


import logging

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, get_biome_palette
from data.configurations import SettlementConfig, TerrainConfig
from data.settlement_entities import Building
from data.settlement_state import SettlementState
from planning.settlement_planner import SettlementPlanner
from structures.house.house import House
from structures.tower.tower import Tower
from structures.farm.farm import Farm
from structures.decoration.decoration import Decoration
from structures.fortification.fortification_builder import FortificationBuilder
from world_interface.road_placer import RoadBuilder
from world_interface.terrain_clearer import remove_sparse_top, seal_cave_openings

logger = logging.getLogger(__name__)


class SettlementGenerator:
    """
    Orchestrates the full settlement generation pipeline:
    planning (districts, roads, plots) followed by structure placement.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        settlement_config: SettlementConfig,
        terrain_config: TerrainConfig,
        palette: BiomePalette | None = None,
    ) -> None:
        self.editor            = editor
        self.analysis          = analysis
        self.settlement_config = settlement_config
        self.terrain_config    = terrain_config
        self.palette           = palette
        self.planner           = SettlementPlanner(analysis, settlement_config)

    def generate(self, num_buildings: int | None = None) -> SettlementState:
        """
        Run the full settlement generation pipeline.

        Args:
            num_buildings: If set, cap the number of plots built (useful for
                           testing). Plots are taken in planning order.

        Returns:
            SettlementState populated with districts, roads, plots, and buildings.
        """
        logger.info("=" * 50)
        logger.info("SETTLEMENT GENERATOR")
        logger.info("=" * 50)

        # --- Phase 1: District planning ---
        logger.info("[Phase 1] District planning...")
        state = self.planner.plan_districts()
        logger.info("  ✓ %d districts ready.", len(state.districts.district_list))

        # --- Phase 2: Terrain cleanup ---
        # Districts are known so per-district plot sizes can be used to decide
        # whether a cluster is large enough to preserve as a build site.
        # Runs before roads and plots so they see the cleaned heightmap.
        logger.info("[Phase 2] Terrain cleanup...")
        remove_sparse_top(
            editor=self.editor,
            analysis=self.analysis,
            districts=state.districts,
            settlement_config=self.settlement_config,
        )
        logger.info("  ✓ Sparse terrain clusters removed.")

        seal_cave_openings(
            editor=self.editor,
            analysis=self.analysis,
        )
        logger.info("  ✓ Cave openings sealed.")

        # Recompute slope and roughness maps from the cleaned heightmap so the
        # plot planner's _valid() checks reflect the updated terrain rather than
        # the original bumpy surface that was just cleaned.
        self._recompute_terrain_maps()
        logger.info("  ✓ Terrain maps recomputed after cleanup.")

        # --- Phase 3: Road and plot planning ---
        logger.info("[Phase 3] Road and plot planning...")
        self.planner.plan_roads_and_plots(state)
        logger.info(
            "  ✓ %d road cells, %d plots ready.",
            state.road_cell_count,
            state.plot_count,
        )

        # --- Phase 4: Road placement ---
        logger.info("[Phase 3] Road placement...")
        palette = self.palette if self.palette is not None else get_biome_palette()
        road_builder = RoadBuilder(
            editor=self.editor,
            analysis=self.analysis,
            palette=palette,
        )
        road_builder.build(state.roads)
        logger.info("  ✓ %d road cells placed.", state.road_cell_count)

        # --- Phase 5: Structure placement ---
        logger.info("[Phase 5] Structure generation...")

        plots_to_build = state.plots
        if num_buildings is not None:
            plots_to_build = plots_to_build[:num_buildings]

        # Determine if water is accessible (any fishing district exists)
        has_water = any(
            dtype == "fishing"
            for dtype in state.districts.types.values()
        )

        # Build structure instances once — shared across all plots of that type
        _palette = self.palette if self.palette is not None else get_biome_palette()
        _structures = {
            "house":      House(self.editor, self.analysis, self.terrain_config, _palette),
            "tower":      Tower(self.editor, self.analysis, self.terrain_config, _palette),
            "farm":       Farm(self.editor, self.analysis, self.terrain_config, _palette),
            "decoration": Decoration(self.editor, self.analysis, self.terrain_config, _palette),
        }

        for idx, plot in enumerate(plots_to_build, 1):
            structure_type = self._select_structure_type(
                plot, state, has_water
            )
            logger.info(
                "  Building %d/%d: %s at (%d, %d).",
                idx, len(plots_to_build), structure_type, plot.x, plot.z,
            )
            _structures[structure_type].build(plot)
            state.add_building(Building(
                x=plot.x, z=plot.z,
                width=plot.width, depth=plot.depth,
                type=structure_type,
            ))

        logger.info("  ✓ %d buildings generated.", state.building_count)

        # --- Phase 6: Fortification ---
        logger.info("[Phase 6] Building fortification...")
        fortification = FortificationBuilder(
            editor=self.editor,
            analysis=self.analysis,
            palette=_palette,
            config=self.settlement_config,
        )
        fortification.build(buildings=state.buildings)
        logger.info("  ✓ Fortification placed.")

        # --- Phase 7: Flush ---
        logger.info("[Phase 7] Flushing blocks to Minecraft...")
        self.editor.flushBuffer()
        logger.info("  ✓ All blocks placed.")

        return state

    def _recompute_terrain_maps(self) -> None:
        """
        Recompute slope_map and roughness_map from the current heightmap_ground.
        Called after terrain cleanup so planners see corrected terrain metrics.
        """
        import numpy as np
        from scipy.ndimage import maximum_filter, minimum_filter

        h    = self.analysis.heightmap_ground.astype(np.float32)
        gx, gz = np.gradient(h)
        self.analysis.slope_map = np.sqrt(gx ** 2 + gz ** 2)

        radius = self.terrain_config.radius
        size   = 2 * radius + 1
        self.analysis.roughness_map = (
            maximum_filter(h, size=size) - minimum_filter(h, size=size)
        )

    def _select_structure_type(
        self,
        plot,
        state,
        has_water: bool,
    ) -> str:
        """
        Select a structure type for a plot based on its district type and the
        configured ratios (60% residential, 20% functional, 10% fishing,
        10% decoration). If no water access, fishing share is redistributed.

        District type acts as the primary constraint:
          - 'farming'     → always farm
          - 'fishing'     → house (fishing structures not yet implemented)
          - 'forest'      → decoration
          - 'residential' → weighted: house / tower / decoration
        """
        import random

        cfg = self.settlement_config

        # plot.type is set by PlotPlanner directly from the district type —
        # this is the correct and only lookup needed.
        dtype = (plot.type or "residential").strip().lower()

        if dtype == "farming":
            return "farm"

        if dtype == "forest":
            return "decoration"

        if dtype == "fishing":
            # Fishing plots get houses until fishing structures are implemented
            return "house"

        # Residential — weighted selection
        r_res  = cfg.ratio_residential
        r_func = cfg.ratio_functional
        r_fish = cfg.ratio_fishing if has_water else 0.0
        r_deco = cfg.ratio_decoration

        # Redistribute fishing share if no water
        if not has_water:
            extra = cfg.ratio_fishing / 3.0
            r_res  += extra
            r_func += extra
            r_deco += extra

        total = r_res + r_func + r_fish + r_deco
        roll  = random.random() * total

        if roll < r_res:
            return "house"
        elif roll < r_res + r_func:
            return "tower"
        elif roll < r_res + r_func + r_fish:
            return "fishing"
        else:
            return "decoration"