"""SettlementGenerator — builds districts, plots, roads, and structures."""
from __future__ import annotations

import logging

import numpy as np
from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, get_biome_palette
from data.configurations import SettlementConfig, TerrainConfig
from data.settlement_entities import Building, Plot, RoadCell
from data.settlement_state import SettlementState
from structures.misc.square_centre import SquareCentre
from planning.palette_mapper import PaletteMapper
from planning.settlement_planner import SettlementPlanner
from structures.base.structure_selector import StructureSelector
from structures.decoration.district.district_marker import DistrictMarker
from structures.fortification.fortification_builder import FortificationBuilder
from world_interface.road_placer import RoadBuilder
from world_interface.terraforming import (
    remove_sparse_top, fill_depressions, clear_area, terraform_perimeter,
    recompute_all_maps,
)

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

        default_palette = self.palette if self.palette is not None else get_biome_palette()

        if self.analysis.water_distances is None:
            from scipy.ndimage import distance_transform_edt
            self.analysis.water_distances = distance_transform_edt(
                ~self.analysis.water_mask.astype(bool)).astype(np.float32)

        # --- Phase 1: District planning ---
        logger.info("[Phase 1] District planning...")
        state = self.planner.plan_districts()
        logger.info("  ✓ %d districts ready.", len(state.districts.district_list))

        # Generate per-district palettes from world biomes
        palette_mapper    = PaletteMapper(self.analysis, state.districts)
        district_palettes = palette_mapper.generate()
        logger.info("  ✓ Per-district palettes generated.")

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

        fill_depressions(
            editor=self.editor,
            analysis=self.analysis,
        )

        logger.info("  ✓ Terrain depressions filled.")

        # Recompute slope and roughness maps from the cleaned heightmap so the
        # plot planner's _valid() checks reflect the updated terrain rather than
        # the original bumpy surface that was just cleaned.
        recompute_all_maps(self.editor, self.analysis, self.terrain_config)
        logger.info("  ✓ All terrain maps recomputed after cleanup.")

        # --- Phase 3a: Placing districts fountains... ---
        district_marker = DistrictMarker(
            editor=self.editor,
            analysis=self.analysis,
            palette=default_palette
        )
        logger.info("[Phase 3a] Placing district fountains...")
        fountain_cells = district_marker.build(state.districts)
        state.add_taken(fountain_cells)
        # Track which district indices received a fountain so selectors
        # can suppress decoration in those districts.
        fountain_district_ids: set[int] = set(range(len(state.districts.district_list)))

        # --- Phase 3a.5: Central plaza ---
        # Plaza center and radius were pre-computed in plan_districts() so that
        # the district planner could exclude the plaza area from district assignment.
        plaza_radius = state.plaza_radius

        if plaza_radius > 0:
            cx, cz = state.plaza_center
            logger.info(
                "[Phase 3a.5] Placing %s plaza (radius=%d) at (%d, %d)...",
                "big" if plaza_radius >= 8 else "small", plaza_radius, cx, cz,
            )
            area   = self.analysis.best_area
            li, lj = area.world_to_index(cx, cz)
            cy     = int(self.analysis.heightmap_ground[li, lj])

            plaza_plot = Plot(
                x=cx - plaza_radius, z=cz - plaza_radius,
                width=plaza_radius * 2, depth=plaza_radius * 2, y=cy,
            )
            SquareCentre().build(self.editor, plaza_plot, palette=default_palette)
            logger.info("  ✓ Plaza structure placed at (%d, %d).", cx, cz)

            # Block everything from the plaza centre out to the ring road
            # centre-line so no plot can squeeze into the gap between the
            # plaza circle and the ring road.
            road_width  = self.settlement_config.road_width
            ring_radius = plaza_radius + road_width + 1
            excl_sq     = ring_radius ** 2
            plaza_taken = {
                (cx + dx, cz + dz)
                for dx in range(-ring_radius, ring_radius + 1)
                for dz in range(-ring_radius, ring_radius + 1)
                if dx ** 2 + dz ** 2 <= excl_sq
            }
            state.add_taken(plaza_taken)

            # Circular ring road around the plaza
            ring_cells = self._generate_ring_road(cx, cz, plaza_radius)
            state.add_road_cells(ring_cells)
            logger.info("  ✓ Ring road generated (%d cells).", len(ring_cells))

        # --- Phase 3a.6: Spire tower at best_area centroid ---
        # One spire tower placed at the geographic centre of the entire build
        # area — not on any plot, not in any district pool.
        area    = self.analysis.best_area
        scx     = area.x_from + area.width  // 2
        scz     = area.z_from + area.depth  // 2
        try:
            sli, slj = area.world_to_index(scx, scz)
            scy      = int(self.analysis.heightmap_ground[sli, slj])
            spire_size = 6
            spire_plot = Plot(
                x=scx - spire_size, z=scz - spire_size,
                width=spire_size * 2, depth=spire_size * 2, y=scy,
            )
            from structures.misc.spire_tower import SpireTower
            SpireTower().build(self.editor, spire_plot, default_palette)
            # Mark spire footprint as taken
            spire_taken = {
                (scx + dx, scz + dz)
                for dx in range(-spire_size - 2, spire_size + 3)
                for dz in range(-spire_size - 2, spire_size + 3)
            }
            state.add_taken(spire_taken)
            logger.info(
                "  ✓ Spire tower placed at best_area centre (%d, %d).", scx, scz
            )
        except Exception:
            logger.warning("  Spire tower placement failed.", exc_info=True)

        # --- Phase 3b: Road planning ---
        self.planner.plan_roads(state)
        road_builder = RoadBuilder(
            editor=self.editor,
            analysis=self.analysis,
            palette=default_palette
        )
        road_builder.build(state.roads)
        logger.info(
            "  ✓ %d road cells ready.",
            state.road_cell_count
        )

        # --- Phase 3c: Plot planning ---
        self.planner.plan_plots(state)
        logger.info(
            "  ✓ %d plot cells ready.",
            state.plot_count,
        )

        # --- Phase 4: Structure placement ---
        logger.info("[Phase 4] Structure generation...")

        plots_to_build = state.plots
        if num_buildings is not None:
            plots_to_build = plots_to_build[:num_buildings]

        # Determine if water is accessible (any fishing district exists)
        has_water = any(
            dtype == "fishing"
            for dtype in state.districts.types.values()
        )

        # One StructureSelector per district, each carrying its own palette
        selectors: dict[int, StructureSelector] = {
            idx: StructureSelector(
                editor=self.editor,
                analysis=self.analysis,
                config=self.settlement_config,
                palette=pal,
                has_water=has_water,
                fountain_district_ids=fountain_district_ids,
            )
            for idx, pal in district_palettes.items()
        }
        _fallback_selector = next(iter(selectors.values()))

        area = self.analysis.best_area

        # Track placed building footprints for overlap checking.
        # PAD by max_snap so grammar dimension snapping (odd-number clamping,
        # 7-11 clamp in HouseGrammar) cannot push blocks outside the recorded
        # footprint and into a neighbour plot.  Max snap = 3 blocks each side.
        placed_footprints: list[tuple[int, int, int, int]] = []  # (x, z, x2, z2)
        _PAD = 3   # blocks — matches worst-case grammar snap + 1 buffer

        for idx, plot in enumerate(plots_to_build, 1):
            # Explicit overlap check against already-placed buildings
            px1 = plot.x - _PAD
            pz1 = plot.z - _PAD
            px2 = plot.x + plot.width - 1 + _PAD
            pz2 = plot.z + plot.depth - 1 + _PAD
            clash = next(
                (
                    (fx1, fz1, fx2, fz2)
                    for fx1, fz1, fx2, fz2 in placed_footprints
                    if px1 <= fx2 and px2 >= fx1 and pz1 <= fz2 and pz2 >= fz1
                ),
                None,
            )
            if clash is not None:
                cfx1, cfz1, cfx2, cfz2 = clash
                logger.debug(
                    "  OVERLAP: plot (%d,%d)–(%d,%d) [padded (%d,%d)–(%d,%d)]"
                    " clashes with footprint (%d,%d)–(%d,%d).",
                    plot.x, plot.z, plot.x + plot.width - 1, plot.z + plot.depth - 1,
                    px1, pz1, px2, pz2,
                    cfx1, cfz1, cfx2, cfz2,
                )
                logger.warning(
                    "  Skipping plot at (%d, %d) — overlaps with existing building.",
                    plot.x, plot.z,
                )
                continue

            # Resolve the district this plot sits in for palette + selector lookup
            try:
                li, lj      = area.world_to_index(plot.x, plot.z)
                district_idx = int(state.districts.map[li, lj])
            except (ValueError, IndexError):
                district_idx = -1

            selector     = selectors.get(district_idx, _fallback_selector)
            template_key = selector.select(plot)

            if template_key is None:
                logger.warning(
                    "  No template for plot %d/%d at (%d, %d) — skipping.",
                    idx, len(plots_to_build), plot.x, plot.z,
                )
                continue

            logger.info(
                "  Building %d/%d: %s at (%d, %d).",
                idx, len(plots_to_build), template_key, plot.x, plot.z,
            )
            clear_area(self.editor, self.analysis, plot, self.terrain_config)

            selector.build(plot, template_key)

            placed_footprints.append((px1, pz1, px2, pz2))
            state.add_building(Building(
                x=plot.x, z=plot.z,
                width=plot.width, depth=plot.depth,
                type=template_key,
            ))

        logger.info("  ✓ %d buildings generated.", state.building_count)

        # --- Phase 6: Fortification ---
        logger.info("[Phase 6] Building fortification...")
        fortification = FortificationBuilder(
            editor=self.editor,
            analysis=self.analysis,
            palette=default_palette,
            config=self.settlement_config,
        )
        fortification.build()
        logger.info("  ✓ Fortification placed.")

        # --- Phase 7: Flush ---
        logger.info("[Phase 7] Flushing blocks to Minecraft...")
        self.editor.flushBuffer()
        logger.info("  ✓ All blocks placed.")

        return state

    def _generate_ring_road(
        self,
        cx: int,
        cz: int,
        plaza_radius: int,
    ) -> list[RoadCell]:
        """
        Return RoadCells forming a circular ring around the plaza.

        The ring centre-line sits at plaza_radius + road_width + 1 from (cx, cz),
        with thickness equal to road_width so it matches the rest of the network.
        """
        road_width  = self.settlement_config.road_width
        ring_radius = plaza_radius + road_width + 1
        half        = road_width // 2
        inner_sq    = (ring_radius - half) ** 2
        outer_sq    = (ring_radius + half) ** 2

        area  = self.analysis.best_area
        cells: set[tuple[int, int]] = set()

        for dx in range(-(ring_radius + half + 1), ring_radius + half + 2):
            for dz in range(-(ring_radius + half + 1), ring_radius + half + 2):
                dist_sq = dx ** 2 + dz ** 2
                if inner_sq <= dist_sq <= outer_sq:
                    wx, wz = cx + dx, cz + dz
                    if area.contains_xz(wx, wz):
                        cells.add((wx, wz))

        return [RoadCell(wx, wz, type="main_road") for wx, wz in cells]