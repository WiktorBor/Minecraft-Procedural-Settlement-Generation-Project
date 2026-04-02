"""SettlementGenerator — builds districts, plots, roads, and structures."""
from __future__ import annotations


import logging
import numpy as np

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, get_biome_palette
from data.configurations import SettlementConfig, TerrainConfig
from data.settlement_entities import Building, RoadCell
from data.settlement_state import SettlementState
from utils.astar import find_path
from utils.walkable_grid import build_cost_grid
from planning.palette_mapper import PaletteMapper
from planning.settlement_planner import SettlementPlanner
from structures.base.registry import get_structure
from structures.base.structure_selector import StructureSelector
from structures.decoration.district_marker import DistrictMarker
from structures.fortification.fortification_builder import FortificationBuilder
from world_interface.road_placer import RoadBuilder
from world_interface.terrain_clearer import remove_sparse_top, clear_lava_pools, clear_area
from world_interface.terraforming import terraform_area

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

        terraform_area(
            editor=self.editor,
            analysis=self.analysis
        )

        logger.info("  ✓ Terrain smoothed.")

        clear_lava_pools(
            editor=self.editor,
            analysis=self.analysis,
        )

        logger.info("  ✓ Surface lava pools cleared.")

        # Recompute slope and roughness maps from the cleaned heightmap so the
        # plot planner's _valid() checks reflect the updated terrain rather than
        # the original bumpy surface that was just cleaned.
        self._recompute_terrain_maps()
        logger.info("  ✓ Terrain maps recomputed after cleanup.")

        # --- Phase 3a: Placing districts fountains... ---
        district_marker = DistrictMarker(
            editor=self.editor,
            analysis=self.analysis,
            palette=default_palette
        )
        logger.info("[Phase 3a] Placing district fountains...")
        fountain_cells = district_marker.build(state.districts)
        state.add_taken(fountain_cells)

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
        _fallback_palette = next(iter(district_palettes.values()))
        selectors: dict[int, StructureSelector] = {
            idx: StructureSelector(
                editor=self.editor,
                analysis=self.analysis,
                config=self.settlement_config,
                palette=pal,
                has_water=has_water,
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

            if template_key in ("farm", "decoration"):
                pal = district_palettes.get(district_idx, _fallback_palette)
                get_structure(template_key)(self.editor, self.analysis, pal).build(plot)
            else:
                selector.build(plot, template_key)

            placed_footprints.append((px1, pz1, px2, pz2))
            state.add_building(Building(
                x=plot.x, z=plot.z,
                width=plot.width, depth=plot.depth,
                type=template_key,
                facing=plot.facing,
            ))

        logger.info("  ✓ %d buildings generated.", state.building_count)

        # --- Phase 5: Building connectors ---
        # For each placed building, run A* from the nearest road cell to the
        # building's front door and place a path using the same road block.
        logger.info("[Phase 5] Placing building connector paths...")
        connector_cells = self._build_connectors(state)
        if connector_cells:
            road_builder.build(connector_cells)
            state.add_road_cells(connector_cells)
        logger.info("  ✓ %d connector cells placed.", len(connector_cells))

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

    def _build_connectors(self, state: SettlementState) -> list[RoadCell]:
        """
        For each placed building, A*-path from the nearest road cell to the
        building's front door and return those cells as RoadCell objects.

        Connector paths are 1-2 blocks wide and use the ``connector`` type so
        the RoadBuilder renders them as narrow village footpaths.
        """
        from utils.path_utils import expand_path_to_width

        area      = self.analysis.best_area
        heightmap = self.analysis.heightmap_ground
        water     = self.analysis.water_mask.astype(bool)

        if not state._road_coords:
            return []

        building_mask = np.zeros(heightmap.shape, dtype=bool)
        for b in state.buildings:
            try:
                li0, lj0 = area.world_to_index(b.x_from, b.z_from)
                li1, lj1 = area.world_to_index(b.x_to,   b.z_to)
                li0, li1 = sorted((li0, li1))
                lj0, lj1 = sorted((lj0, lj1))
                building_mask[li0:li1 + 1, lj0:lj1 + 1] = True
            except ValueError:
                pass

        walkable  = ~water & ~building_mask
        costs     = build_cost_grid(water, additional_blocked=building_mask)

        road_bonus = np.zeros(heightmap.shape, dtype=np.float32)
        for rx, rz in state._road_coords:
            try:
                li, lj = area.world_to_index(rx, rz)
                road_bonus[li, lj] = -0.8
            except ValueError:
                pass
        costs = np.maximum(0.1, costs + road_bonus)

        all_connectors: list[RoadCell] = []
        already_placed: set[tuple[int, int]] = set()

        for building in state.buildings:
            # Find the nearest road cell to the building center, then find the
            # perimeter cell on the side closest to that road.  This ensures the
            # connector path reaches whichever side of the building actually
            # faces the road — regardless of the facing field.
            bcx = int(building.center_x)
            bcz = int(building.center_z)

            nearest_rx, nearest_rz = min(
                state._road_coords,
                key=lambda r: abs(r[0] - bcx) + abs(r[1] - bcz),
            )

            # Build perimeter ring 1 block outside the building footprint.
            perimeter: list[tuple[int, int]] = []
            for px in range(building.x_from - 1, building.x_to + 2):
                perimeter.append((px, building.z_from - 1))
                perimeter.append((px, building.z_to + 1))
            for pz in range(building.z_from, building.z_to + 1):
                perimeter.append((building.x_from - 1, pz))
                perimeter.append((building.x_to + 1, pz))

            door_wx, door_wz = min(
                perimeter,
                key=lambda p: abs(p[0] - nearest_rx) + abs(p[1] - nearest_rz),
            )

            try:
                door_li, door_lj = area.world_to_index(door_wx, door_wz)
            except ValueError:
                continue

            door_li = int(np.clip(door_li, 0, walkable.shape[0] - 1))
            door_lj = int(np.clip(door_lj, 0, walkable.shape[1] - 1))
            walkable[door_li, door_lj] = True

            try:
                road_li, road_lj = area.world_to_index(nearest_rx, nearest_rz)
            except ValueError:
                continue

            walkable[road_li, road_lj] = True

            path = find_path(
                walkable, heightmap,
                start=(road_li, road_lj),
                goal=(door_li, door_lj),
                height_step_max=3,
                height_cost=0.3,
                costs=costs,
            )

            if path is None:
                logger.debug(
                    "  No connector path to building at (%d, %d).",
                    building.x, building.z,
                )
                continue

            # Convert A* local path to world coordinates.
            centerline: set[tuple[int, int]] = set()
            for li, lj in path:
                wx, wz = area.index_to_world(li, lj)
                if (wx, wz) not in state._road_coords:
                    centerline.add((wx, wz))

            # Expand to 2-wide with organic edges so it looks like a
            # worn footpath rather than a single-pixel line.
            bounds = (area.x_from, area.x_to, area.z_from, area.z_to)
            expanded = expand_path_to_width(
                centerline, 2, bounds,
                blocked=set(),
                organic=True,
            )

            for wx, wz in expanded:
                if (wx, wz) not in already_placed and (wx, wz) not in state._road_coords:
                    all_connectors.append(RoadCell(wx, wz, type="connector"))
                    already_placed.add((wx, wz))

        logger.info(
            "_build_connectors: %d connector cells for %d buildings.",
            len(all_connectors), len(state.buildings),
        )
        return all_connectors

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

