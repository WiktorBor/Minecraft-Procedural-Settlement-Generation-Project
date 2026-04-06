"""SettlementGenerator — builds districts, plots, roads, and structures."""
from __future__ import annotations

import logging
import math
import random

import numpy as np
from gdpc.editor import Editor

from analysis.world_analysis import WorldAnalyser
from data.biome_palettes import BiomePalette
from data.configurations import TerrainConfig, SettlementConfig
from data.settlement_entities import Building, Plot, RoadCell
from data.settlement_state import SettlementState
from structures.misc.square_centre import SquareCentre
from utils.astar import find_path
from utils.walkable_grid import build_cost_grid
from data.palette_system import PaletteSystem
from planning.settlement_planner import SettlementPlanner
from structures.base.structure_selector import StructureSelector
from structures.decoration.district.district_marker import DistrictMarker
from structures.fortification.fortification_builder import FortificationBuilder
from world_interface.block_buffer import BlockBuffer
from world_interface.road_placer import RoadBuilder
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

        logger.info("[Phase 1] Filling terrain holes...")
        fill_depressions(editor=self.editor, analysis=analysis, config=self.terrain_config)
        self.editor.flushBuffer()
        recompute_all_maps(
            self.editor, analysis, self.terrain_config,
            terrain_loader=self.analyser.fetcher.terrain,
        )
        logger.info("  ✓ Terrain prepared.")

        # --- Phase 2: District planning + palettes ---
        logger.info("[Phase 2] District planning...")
        state = self.planner.plan_districts(analysis)
        state.init_occupancy(analysis.best_area)
        logger.info("  ✓ %d districts ready.", len(state.districts.district_list))

        district_palettes = PaletteSystem().generate(analysis, state.districts)
        default_palette   = next(iter(district_palettes.values()))
        logger.info("  ✓ Per-district palettes generated.")

        master_buffer = BlockBuffer()

        # --- Phase 3a: Central plaza ---
        plaza_radius = state.plaza_radius
        if plaza_radius > 0:
            cx, cz = state.plaza_center
            logger.info(
                "[Phase 3a] Placing %s plaza (radius=%d) at (%d, %d)...",
                "big" if plaza_radius >= 8 else "small", plaza_radius, cx, cz,
            )
            area   = analysis.best_area
            li, lj = area.world_to_index(cx, cz)
            cy     = int(analysis.heightmap_ground[li, lj])

            plaza_plot = Plot(
                x=cx - plaza_radius, z=cz - plaza_radius,
                width=plaza_radius * 2, depth=plaza_radius * 2, y=cy,
            )
            plaza_buf = SquareCentre().build(self.editor, plaza_plot, palette=default_palette)
            if plaza_buf is not None:
                master_buffer.merge(plaza_buf)

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
            logger.info("  ✓ Plaza + ring road placed (%d cells).", len(ring_cells))

        # --- Phase 3b: District markers (fountains / docks) ---
        logger.info("[Phase 3b] Placing district markers...")
        district_marker = DistrictMarker(
            analysis=analysis,
            palette=default_palette,
        )
        marker_buffer, fountain_cells = district_marker.build(state.districts)
        master_buffer.merge(marker_buffer)
        state.add_taken(fountain_cells)

        # --- Phase 3c: Central landmark tower ---
        tower_buf, tower_taken = self._place_central_tower(state, default_palette, analysis)
        if tower_buf is not None:
            master_buffer.merge(tower_buf)
        if tower_taken:
            state.add_taken(tower_taken)

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
            # Try to resolve district from the plot centre (more reliable than
            # the corner which may land on a road or border cell).
            pcx = plot.x + plot.width  // 2
            pcz = plot.z + plot.depth  // 2
            try:
                li, lj       = area.world_to_index(pcx, pcz)
                district_idx = int(state.districts.map[li, lj])
            except (ValueError, IndexError):
                district_idx = -1

            # If map lookup still gave nothing, fall back to the type stored on
            # the plot at planning time.
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

            logger.info(
                "  Building %d/%d: %s at (%d, %d).",
                idx, len(state.plots), template_key, plot.x, plot.z,
            )

            level_plot_area(self.editor, analysis, plot)
            buf = selector.build(plot, template_key)
            if buf is None:
                logger.warning(
                    "  Builder '%s' failed at (%d,%d) size=%dx%d facing=%s "
                    "— check ERROR logs from structures.base.structure_selector.",
                    template_key, plot.x, plot.z,
                    plot.width, plot.depth, plot.facing,
                )
            elif len(buf) == 0:
                logger.warning(
                    "  Builder '%s' returned empty buffer at (%d,%d) — skipping.",
                    template_key, plot.x, plot.z,
                )
            else:
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
        fort_buf = FortificationBuilder(
            analysis=analysis,
            palette=default_palette,
            config=self.settlement_config,
        ).build(state.buildings)
        master_buffer.merge(fort_buf)
        logger.info("  ✓ Fortification placed.")

        # --- Phase 7: Flush via StructurePlacer ---
        logger.info("[Phase 7] Flushing blocks to Minecraft...")
        StructurePlacer(self.editor).place(master_buffer)
        logger.info("  ✓ All blocks placed.")

        return state

    def _place_central_tower(
        self,
        state: SettlementState,
        palette: BiomePalette,
        analysis,
    ) -> set[tuple[int, int]] | None:
        """
        Optionally place one landmark tower somewhere near the settlement centre.

        Tower type and position are chosen with aesthetic rules so the result
        feels hand-placed rather than mechanically centred:

        Type selection (weighted)
        -------------------------
        - SpireTower  (40 %) — tall stone spire + house wing; looks best on a
                               slight high point; needs a 10×6 footprint.
        - ClockTower  (35 %) — compact civic landmark; fits any 8×8 space and
                               works well near the plaza.
        - None        (25 %) — some settlements have no dominant tower, which
                               adds variety between runs.

        Position selection
        ------------------
        Candidates are sampled in a ring around the best_area centroid at radii
        8–25 blocks (avoids the plaza, isn't on the very edge).  Each candidate
        is scored by how much it rises above the local median height — a slight
        elevation makes the tower look naturally placed on a hill.  The highest-
        scoring candidate that doesn't overlap taken cells is used.  If no
        candidate scores above 0 the centroid itself is tried as a fallback.

        Returns the set of (x, z) cells occupied by the tower, or None if no
        tower was placed.
        """
        # --- Roll tower type ---
        roll = random.random()
        if roll < 0.25:
            logger.info("[Phase 3a.6] No central tower this run (25%% chance).")
            return None, None
        elif roll < 0.65:
            tower_type = "spire"
            min_w, min_d = 10, 6
        else:
            tower_type = "clock"
            min_w, min_d = 8, 8

        area = analysis.best_area
        hmap = analysis.heightmap_ground

        # best_area centroid in world coords
        cent_x = (area.x_from + area.x_to) // 2
        cent_z = (area.z_from + area.z_to) // 2

        # Compute median height across the whole area for elevation scoring
        median_y = int(np.median(hmap))

        # --- Candidate search: ring of radii 8–25 around centroid ---
        def _footprint_clear(wx: int, wz: int, fw: int, fd: int) -> bool:
            """True if no occupied cell overlaps the footprint + 2-block buffer."""
            for dx in range(-2, fw + 2):
                for dz in range(-2, fd + 2):
                    if (wx + dx, wz + dz) in state.occupancy:
                        return False
            return True

        best_pos   = None
        best_score = -999

        step = 4  # angular step size — enough candidates without being slow
        for radius in range(8, 26, 4):
            for angle_step in range(0, 360, step):
                rad = math.radians(angle_step)
                wx  = cent_x + int(round(radius * math.cos(rad)))
                wz  = cent_z + int(round(radius * math.sin(rad)))

                if not area.contains_xz(wx, wz):
                    continue
                if not area.contains_xz(wx + min_w - 1, wz + min_d - 1):
                    continue

                li = wx - area.x_from
                lj = wz - area.z_from
                if not (0 <= li < hmap.shape[0] and 0 <= lj < hmap.shape[1]):
                    continue

                ground_y = int(hmap[li, lj])
                # Prefer cells that are slightly above median (1–4 blocks) —
                # that's a natural hilltop.  Penalise very high (cliff) or
                # very low (valley) positions.
                elev_diff = ground_y - median_y
                if elev_diff < 0:
                    score = elev_diff * 2        # strong penalty for valleys
                elif 1 <= elev_diff <= 4:
                    score = elev_diff * 3 + 5    # sweet spot: gentle hill
                elif elev_diff <= 8:
                    score = 10 - elev_diff       # acceptable but not ideal
                else:
                    score = -elev_diff           # cliff — penalise

                # Small random jitter so identical-height candidates don't
                # always resolve to the same compass direction each run
                score += random.uniform(-0.5, 0.5)

                if score > best_score and _footprint_clear(wx, wz, min_w, min_d):
                    best_score = score
                    best_pos   = (wx, wz)

        # Fallback to centroid if no candidate found
        if best_pos is None:
            if _footprint_clear(cent_x, cent_z, min_w, min_d):
                best_pos = (cent_x, cent_z)
            else:
                logger.info("[Phase 3a.6] No clear position for central tower — skipping.")
                return None, None

        wx, wz = best_pos
        li     = wx - area.x_from
        lj     = wz - area.z_from
        wy     = int(hmap[li, lj])

        plot = Plot(x=wx, z=wz, y=wy, width=min_w, depth=min_d, type="landmark")

        logger.info(
            "[Phase 3a.6] Placing central %s tower at (%d, %d) y=%d  "
            "(elev_score=%.1f).",
            tower_type, wx, wz, wy, best_score,
        )

        try:
            if tower_type == "spire":
                from structures.misc.spire_tower import SpireTower
                tower_buf = SpireTower().build(self.editor, plot, palette, analysis=analysis)
            else:
                from structures.misc.clock_tower import ClockTower
                tower_buf = ClockTower().build(self.editor, plot, palette)
        except Exception:
            logger.error(
                "[Phase 3a.6] Central tower builder failed at (%d, %d).",
                wx, wz, exc_info=True,
            )
            return None, None

        footprint = {
            (wx + dx, wz + dz)
            for dx in range(min_w)
            for dz in range(min_d)
        }
        return tower_buf, footprint

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

        # Also block all occupied cells (tower, plaza, fountains, dock, plots) so
        # connector paths never route through structures placed outside
        # the normal plot/building pipeline.
        for wx, wz in state.occupancy:
            if (wx, wz) in state._road_coords:
                continue  # roads are occupied too — keep them walkable
            try:
                li, lj = area.world_to_index(wx, wz)
                building_mask[li, lj] = True
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
            "_build_connectors: %d connector cells for %d buildings "
            "(%d already on road, %d no path found).",
            len(all_connectors), len(state.buildings),
            already_on_road, no_path_count,
        )
        return all_connectors