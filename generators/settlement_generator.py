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
from world_interface.road_placer import RoadBuilder
from world_interface.terrain_clearer import remove_sparse_top

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

        # Construct House once — editor, analysis, and config are shared across all plots
        house = House(
            editor=self.editor,
            analysis=self.analysis,
            terrain_config=self.terrain_config,
            palette=self.palette,
        )

        for idx, plot in enumerate(plots_to_build, 1):
            logger.info("  Building %d/%d at (%d, %d).", idx, len(plots_to_build), plot.x, plot.z)
            house.build(plot)
            state.add_building(Building(
                x=plot.x,
                z=plot.z,
                width=plot.width,
                depth=plot.depth,
                type="house",
            ))

        logger.info("  ✓ %d buildings generated.", state.building_count)

        # --- Phase 6: Flush ---
        logger.info("[Phase 6] Flushing blocks to Minecraft...")
        self.editor.flushBuffer()
        logger.info("  ✓ All blocks placed.")

        return state