"""SettlementGenerator — builds districts, plots, roads, and structures."""
from __future__ import annotations

import logging
import math
import random
from dataclasses import replace

import numpy as np
from gdpc.editor import Editor

from analysis.world_analysis import WorldAnalyser
from data.configurations import TerrainConfig, SettlementConfig
from data.settlement_entities import Building, Plot, RoadCell
from data.settlement_state import SettlementState
from utils.astar import find_path
from utils.walkable_grid import build_cost_grid
from palette.palette_system import PaletteSystem
from planning.settlement_planner import SettlementPlanner
from structures.base.build_context import BuildContext
from structures.structure_selector import StructureSelector
from structures.district_structures.district_marker import DistrictMarker
from world_interface.block_buffer import BlockBuffer
from planning.infrastructure.road_placer import RoadBuilder
from world_interface.structure_placer import StructurePlacer
from world_interface.terraforming import fill_depressions, level_plot_area, recompute_all_maps

logger = logging.getLogger(__name__)


class SettlementGenerator:
    """
    Orchestrates the full settlement generation pipeline:
    planning (districts, roads, plots) followed by structure placement.
    """

    def __init__(
        self,
        editor:   Editor,
        analyser: WorldAnalyser,
        settlement_config: SettlementConfig,
        terrain_config:   TerrainConfig,
        planner:  SettlementPlanner,
    ) -> None:
        self.editor       = editor
        self.analyser     = analyser
        self.settlement_config = settlement_config
        self.terrain_config    = terrain_config
        self.planner      = planner

    def generate(self) -> SettlementState:
        """Run the full settlement generation pipeline."""
        logger.info("=" * 50)
        logger.info("SETTLEMENT GENERATOR")
        logger.info("=" * 50)

        # --- Phase 1: World analysis + terrain fill ---
        logger.info("[Phase 1] Analysing world...")
        analysis = self.analyser.prepare()
        logger.info("  ✓ World analysis complete. Best area: %s", analysis.best_area)

        # --- Phase 2: District planning + palettes ---
        logger.info("[Phase 2] District planning...")
        state = self.planner.plan_districts(analysis)
        state.init_occupancy(analysis.best_area)
        logger.info("  ✓ %d districts ready.", len(state.districts.district_list))

        district_palettes = PaletteSystem().generate(analysis, state.districts)
        default_palette   = next(iter(district_palettes.values()))
        logger.info("  ✓ Per-district palettes generated.")

        master_buffer = BlockBuffer()
        # Initialize a shared BuildContext for the master settlement buffer
        self.ctx = BuildContext(buffer=master_buffer, palette=default_palette)

        # --- Phase 3: Civic Landmark (Plaza) ---
        area = analysis.best_area
        total_settlement_area = area.width * area.depth
        
        # Calculate potential plaza dimensions
        plaza_radius = state.plaza_radius
        plaza_side = plaza_radius * 2
        plaza_area = plaza_side * plaza_side

        if plaza_radius > 0 and (plaza_area / total_settlement_area) <= 0.15:
            cx, cz = state.plaza_center
            logger.info(
                "[Phase 3a] Placing %s plaza (radius=%d) at (%d, %d)..."
            )
            li, lj = area.world_to_index(cx, cz)
            cy     = int(analysis.heightmap_ground[li, lj])

            plaza_plot = Plot(
                x=cx - plaza_radius, z=cz - plaza_radius,
                width=plaza_side, depth=plaza_side, y=cy,
                type="plaza"
            )

            level_plot_area(self.editor, analysis, plaza_plot)
            from structures.orchestrators.plaza import build_square_centre
            build_square_centre(self.ctx, plaza_plot)

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

            ring_cells = self._generate_ring_road(cx, cz, plaza_radius, analysis, road_width)
            state.add_road_cells(ring_cells)
            state.add_taken({(c.x, c.z) for c in ring_cells})
            logger.info("  ✓ Plaza + ring road placed (%d cells).", len(ring_cells))
        else:
            logger.info(
                "[Phase 3a] Skipping plaza: radius=%d too large for area (%.2f%%).",
                plaza_radius, (plaza_area / total_settlement_area) * 100
            )

        # --- Phase 3b: District markers (fountains / wells / docks) ---
        logger.info("[Phase 3b] Placing district markers...")
        
        # FIX: Pass self.ctx instead of palette
        district_marker = DistrictMarker(
            analysis=analysis,
            ctx=self.ctx,
        )
        # build() now writes to master_buffer via ctx and returns ONLY taken cells
        fountain_cells = district_marker.build(state.districts)
        state.add_taken(fountain_cells)
        logger.info("  ✓ District markers placed (%d cells).", len(fountain_cells))

        # --- Phase 3d: Road planning + placement ---
        logger.info("[Phase 3d] Planning roads...")
        self.planner.plan_roads(analysis, state)
        road_builder = RoadBuilder(
            analysis=analysis,
            palette=default_palette,
        )
        road_buf = road_builder.build(state.roads)
        master_buffer.merge(road_buf)
        logger.info("  ✓ %d road cells placed.", state.road_cell_count)

        # --- Phase 3e: Plot planning ---
        logger.info("[Phase 3e] Planning plots...")
        self.planner.plan_plots(analysis, state)
        logger.info("  ✓ %d plots ready.", state.plot_count)

        # --- Phase 4: Structure placement ---
        logger.info("[Phase 4] Placing structures...")
        has_water = any(dtype == "fishing" for dtype in state.districts.types.values())

        selectors: dict[int, StructureSelector] = {
            idx: StructureSelector(
                analysis=analysis,
                config=self.settlement_config,
                palette=pal,
                has_water=has_water,
            )
            for idx, pal in district_palettes.items()
        }
        _fallback_selector = next(iter(selectors.values()))
        area = analysis.best_area

        for idx, plot in enumerate(state.plots, 1):
            pcx = plot.x + plot.width  // 2
            pcz = plot.z + plot.depth  // 2
            try:
                li, lj       = area.world_to_index(pcx, pcz)
                district_idx = int(state.districts.map[li, lj])
            except (ValueError, IndexError):
                district_idx = -1

            if district_idx not in selectors:
                dtype = (plot.type or "residential").strip().lower()
                district_idx = next(
                    (k for k, v in state.districts.types.items() if v == dtype),
                    -1,
                )

            dtype = state.districts.types.get(district_idx, plot.type or "?")

            logger.info(
                "  Plot %d/%d: district=%s  size=%dx%d  y=%d  facing=%s",
                idx, len(state.plots),
                dtype,
                plot.width, plot.depth, plot.y, plot.facing,
            )

            selector     = selectors.get(district_idx, _fallback_selector)
            template_key = selector.select(plot)

            if template_key is None:
                logger.warning(
                    "  No template for plot %d/%d at (%d, %d) — skipping.",
                    idx, len(state.plots), plot.x, plot.z,
                )
                continue

            max_w = self.settlement_config.max_plot_width
            max_d = self.settlement_config.max_plot_depth
            if plot.width > max_w or plot.depth > max_d:
                plot.width = min(plot.width, max_w)
                plot.depth = min(plot.depth, max_d)
                logger.debug(
                    "  Plot %d/%d clamped to %dx%d.",
                    idx, len(state.plots), plot.width, plot.depth,
                )

            logger.info(
                "  Building %d/%d: %s at (%d, %d).",
                idx, len(state.plots), template_key, plot.x, plot.z,
            )

            struct_w, struct_d = selector.effective_footprint(plot, template_key)
            if struct_w < plot.width or struct_d < plot.depth:
                level_target = replace(plot, width=struct_w, depth=struct_d)
                level_plot_area(self.editor, analysis, level_target)
                plot.y = level_target.y
            else:
                level_plot_area(self.editor, analysis, plot)
            
            self.editor.flushBuffer()

            # Pass context to selectors where refactored, otherwise merge results
            buf = selector.build(plot, template_key)
            if buf is not None and len(buf) > 0:
                master_buffer.merge(buf)

            state.add_building(Building(
                x=plot.x, z=plot.z,
                width=plot.width, depth=plot.depth,
                type=template_key,
                facing=plot.facing,
            ))

        logger.info("  ✓ %d buildings placed.", state.building_count)

        # --- Phase 5: Connector paths ---
        logger.info("[Phase 5] Placing connector paths...")
        connector_cells = self._build_connectors(state, analysis)
        if connector_cells:
            connector_buf = road_builder.build(connector_cells)
            master_buffer.merge(connector_buf)
            state.add_road_cells(connector_cells)
        logger.info("  ✓ %d connector cells placed.", len(connector_cells))

        # --- Phase 6: Fortification ---
        logger.info("[Phase 6] Building fortification...")
        from structures.orchestrators.fortification import build_fortification_settlement
        # Reuse existing master context
        wall_top_y = int(np.max(analysis.heightmap_ground)) + 10
        build_fortification_settlement(
            self.ctx, default_palette,
            analysis.heightmap_ground, analysis.best_area,
            wall_top_y, buildings=state.buildings,
        )
        logger.info("  ✓ Fortification placed.")

        # --- Phase 7: Flush via StructurePlacer ---
        logger.info("[Phase 7] Flushing blocks to Minecraft...")
        StructurePlacer(self.editor).place(master_buffer)
        logger.info("  ✓ All blocks placed.")

        return state

    def _generate_ring_road(
        self,
        cx: int,
        cz: int,
        plaza_radius: int,
        analysis,
        road_width: int = None,
    ) -> list[RoadCell]:
        """
        Return RoadCells forming a circular ring around the plaza.

        The ring centre-line sits at plaza_radius + road_width + 1 from (cx, cz),
        with thickness equal to road_width so it matches the rest of the network.
        """
        ring_radius = plaza_radius + road_width + 1
        half        = road_width // 2
        inner_sq    = (ring_radius - half) ** 2
        outer_sq    = (ring_radius + half) ** 2

        area  = analysis.best_area
        cells: set[tuple[int, int]] = set()

        for dx in range(-(ring_radius + half + 1), ring_radius + half + 2):
            for dz in range(-(ring_radius + half + 1), ring_radius + half + 2):
                dist_sq = dx ** 2 + dz ** 2
                if inner_sq <= dist_sq <= outer_sq:
                    wx, wz = cx + dx, cz + dz
                    if area.contains_xz(wx, wz):
                        cells.add((wx, wz))

        return [RoadCell(wx, wz, type="main_road") for wx, wz in cells]

    def _build_connectors(self, state: SettlementState, analysis) -> list[RoadCell]:
        """
        For each placed building, A*-path from the nearest road cell to the
        building's front door and return those cells as RoadCell objects.

        Connector paths are 1-2 blocks wide and use the ``connector`` type so
        the RoadBuilder renders them as narrow village footpaths.
        """
        from utils.path_utils import expand_path_to_width

        area      = analysis.best_area
        heightmap = analysis.heightmap_ground
        water     = analysis.water_mask.astype(bool)

        if not state._road_coords:
            return []

        # Only block water — connector paths may freely cross plot open ground.
        # Marking every plot footprint as blocked leaves no walkable space for A*.
        walkable  = ~water
        costs     = build_cost_grid(water)

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

        no_path_count    = 0
        already_on_road  = 0

        for building in state.buildings:
            # Use the building's actual door position (derived from facing).
            door_wx, door_wz = building.front_door()

            # If the door cell is already a road cell no connector is needed.
            if (door_wx, door_wz) in state._road_coords:
                already_on_road += 1
                continue

            # Find the nearest road cell to the door (not the building centre).
            nearest_rx, nearest_rz = min(
                state._road_coords,
                key=lambda r: abs(r[0] - door_wx) + abs(r[1] - door_wz),
            )
            nearest_dist = abs(nearest_rx - door_wx) + abs(nearest_rz - door_wz)

            try:
                door_li, door_lj = area.world_to_index(door_wx, door_wz)
            except ValueError:
                logger.debug(
                    "  Door (%d,%d) of building at (%d,%d) outside area — skipping.",
                    door_wx, door_wz, building.x, building.z,
                )
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
                no_path_count += 1
                logger.warning(
                    "  No connector path: building(%s) at (%d,%d) facing=%s "
                    "door=(%d,%d) nearest_road=(%d,%d) dist=%d.",
                    building.type, building.x, building.z, building.facing,
                    door_wx, door_wz, nearest_rx, nearest_rz, nearest_dist,
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
            bounds = analysis.best_area
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
            "_build_connectors: %d connector cells for %d buildings "
            "(%d already on road, %d no path found).",
            len(all_connectors), len(state.buildings),
            already_on_road, no_path_count,
        )
        return all_connectors