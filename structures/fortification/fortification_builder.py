from __future__ import annotations

import logging
from typing import Iterable

from gdpc import Block

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, palette_get
from data.build_area import BuildArea
from data.configurations import SettlementConfig
from data.settlement_entities import Building
from structures.tower.tower_builder import TowerBuilder
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)

# How many blocks below the sampled ground Y to extend the foundation.
# A deeper footing ensures the wall contacts the actual terrain even when the
# heightmap value is a clamped edge-pixel for positions outside best_area.
_FOUND_DEPTH: int = 6


class FortificationBuilder:
    """
    Places four corner towers connected by thick crenellated walls with a gate.

    Key design decisions
    --------------------
    - Wall segments walk between tower FACES, not tower origins, so they
      connect flush without entering the tower footprint.
    - Each step is checked against all tower bounding boxes — any column
      that falls inside a tower is skipped entirely.
    - Each step is also checked against placed building footprints so the
      wall never cuts through a house or farm.
    - Wall is wall_thickness blocks deep perpendicular to its run axis.
    - South wall gets a gate arch with portcullis bars and a hanging lantern.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        palette: BiomePalette,
        config: SettlementConfig,
    ) -> None:
        self.analysis = analysis
        self.palette  = palette
        self.config   = config

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, buildings: Iterable[Building] | None = None) -> BlockBuffer:
        """
        Place the full fortification.

        Parameters
        ----------
        buildings : iterable of Building, optional
            Already-placed structures whose footprints the wall must avoid.
        """
        buffer    = BlockBuffer()
        area      = self.analysis.best_area
        heightmap = self.analysis.heightmap_ground
        cfg       = self.config

        tw = cfg.tower_width
        wh = cfg.wall_height
        wt = cfg.wall_thickness
        gw = getattr(cfg, "gate_width", 4)

        wall_block   = self.palette["wall"]
        accent_block = self.palette["accent"]
        found_block  = self.palette["foundation"]
        light_block  = palette_get(self.palette, "light",     "minecraft:lantern")
        window_block = palette_get(self.palette, "window",    "minecraft:iron_bars")

        corners = self._corner_positions(area, tw)

        tower_boxes = [
            (cx, cz, cx + tw - 1, cz + tw - 1)
            for cx, cz in corners
        ]

        building_boxes: list[tuple[int, int, int, int]] = []
        if buildings:
            for b in buildings:
                building_boxes.append((
                    b.x - 1, b.z - 1,
                    b.x + b.width, b.z + b.depth,
                ))

        wall_sides = [
            ("north", False),
            ("south", True),
            ("east",  False),
            ("west",  False),
        ]

        # ------------------------------------------------------------------
        # Pre-scan: collect every wall column's ground Y across ALL segments
        # so we can pick one uniform wall-top Y for the entire fortification.
        # ------------------------------------------------------------------
        all_gy: list[int] = []
        wall_midlines: list[tuple[int, int, int, int]] = []
        for side, _ in wall_sides:
            ml = self._wall_midline(area, side, tw)
            wall_midlines.append(ml)
            sx, sz, ex, ez = ml
            dx_seg = ex - sx
            dz_seg = ez - sz
            steps  = max(abs(dx_seg), abs(dz_seg))
            if steps == 0:
                continue
            for step in range(steps + 1):
                t  = step / max(steps, 1)
                wx = int(sx + round(t * dx_seg))
                wz = int(sz + round(t * dz_seg))
                if self._in_box(wx, wz, tower_boxes):
                    continue
                if self._in_box(wx, wz, building_boxes):
                    continue
                all_gy.append(self._sample_ground_y(wx, wz, area, heightmap))

        # Also collect the four corner tower ground Ys.
        for cx, cz in corners:
            all_gy.append(self._sample_ground_y(cx, cz, area, heightmap))

        # Pick the 2nd highest unique Y as the global reference so one
        # extreme outlier peak doesn't force everything to a crazy height.
        unique_gy = sorted(set(all_gy), reverse=True)
        if len(unique_gy) >= 2:
            uniform_base_y = unique_gy[1]
        else:
            uniform_base_y = unique_gy[0] if unique_gy else 0

        wall_top_y = uniform_base_y + wh
        logger.info("Fortification: uniform_base_y=%d  wall_top_y=%d  (from %d columns)",
                     uniform_base_y, wall_top_y, len(all_gy))

        # Corner towers — stone body extends 2 blocks above wall_top_y so towers
        # are always visually taller than the connecting walls.
        # Foundation fill mirrors the wall logic (_FOUND_DEPTH blocks below ground).
        for cx, cz in corners:
            corner_ground_y = self._sample_ground_y(cx, cz, area, heightmap)
            body_h = wall_top_y + 2 - corner_ground_y
            tower_buf = TowerBuilder(
                None, self.palette, height=body_h, width=tw,
            ).build_at(cx, corner_ground_y, cz)
            buffer.merge(tower_buf)

            # Extend foundation below each column of the tower footprint so the
            # body connects to the ground even on uneven terrain outside best_area.
            for dx in range(tw):
                for dz in range(tw):
                    for dy in range(1, _FOUND_DEPTH + 1):
                        buffer.place(cx + dx, corner_ground_y - dy, cz + dz,
                                     Block(found_block))

        # Wall segments — all share the same wall_top_y
        for (side, has_gate), (sx, sz, ex, ez) in zip(wall_sides, wall_midlines):
            self._build_wall_segment(
                buffer,
                sx, sz, ex, ez,
                area, heightmap,
                wall_top_y, wt, gw,
                wall_block, accent_block, found_block,
                light_block, window_block,
                tower_boxes=tower_boxes,
                building_boxes=building_boxes,
                has_gate=has_gate,
            )

        logger.info("Fortification: 4 towers + 4 walls + 1 gate.")
        return buffer

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _corner_positions(area: BuildArea, tw: int) -> list[tuple[int, int]]:
        """
        [NW, NE, SW, SE] tower origins positioned so the tower inner corner
        is exactly flush with the best_area corner.
        """
        return [
            (area.x_from - tw,  area.z_from - tw),
            (area.x_to   + 1,   area.z_from - tw),
            (area.x_from - tw,  area.z_to   + 1 ),
            (area.x_to   + 1,   area.z_to   + 1 ),
        ]

    @staticmethod
    def _wall_midline(
        area: BuildArea,
        side: str,
        tw: int,
    ) -> tuple[int, int, int, int]:
        """
        Return (start_x, start_z, end_x, end_z) for a wall segment running
        along the tower midline for a given side of the best_area.
        """
        mid = tw // 2

        if side == "north":
            wz = area.z_from - mid - 1
            return area.x_from, wz, area.x_to, wz
        elif side == "south":
            wz = area.z_to + mid + 1
            return area.x_from, wz, area.x_to, wz
        elif side == "west":
            wx = area.x_from - mid - 1
            return wx, area.z_from, wx, area.z_to
        else:  # east
            wx = area.x_to + mid + 1
            return wx, area.z_from, wx, area.z_to

    @staticmethod
    def _sample_ground_y(
        wx: int,
        wz: int,
        area: BuildArea,
        heightmap,
    ) -> int:
        """
        Return the best estimate of ground Y at world position (wx, wz).

        For positions inside best_area the heightmap value is accurate.
        For positions outside (wall/tower positions beyond the area boundary)
        the raw index would be clamped to an edge pixel, which can be several
        blocks *above* the actual terrain.  To avoid floating walls we take
        the minimum of a small neighbourhood of edge pixels, which errs on
        the side of lower rather than higher.
        """
        li_raw = wx - area.x_from
        lj_raw = wz - area.z_from
        h, d   = heightmap.shape

        inside = (0 <= li_raw < h) and (0 <= lj_raw < d)
        if inside:
            return int(heightmap[li_raw, lj_raw])

        # Outside: scan a 3×3 neighbourhood of the nearest edge pixel
        # and take the minimum so the wall never floats.
        li0 = max(0, min(h - 1, li_raw))
        lj0 = max(0, min(d - 1, lj_raw))
        min_y = int(heightmap[li0, lj0])
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                ni = max(0, min(h - 1, li0 + di))
                nj = max(0, min(d - 1, lj0 + dj))
                v  = int(heightmap[ni, nj])
                if v < min_y:
                    min_y = v
        return min_y

    @staticmethod
    def _in_box(
        wx: int,
        wz: int,
        boxes: list[tuple[int, int, int, int]],
        thickness: int = 0,
    ) -> bool:
        """Return True if (wx, wz) falls inside any box."""
        for x0, z0, x1, z1 in boxes:
            if x0 - thickness <= wx <= x1 + thickness and \
               z0 - thickness <= wz <= z1 + thickness:
                return True
        return False

    # ------------------------------------------------------------------
    # Wall segment dispatcher
    # ------------------------------------------------------------------

    def _build_wall_segment(
        self,
        buffer: BlockBuffer,
        ax: int, az: int,
        bx: int, bz: int,
        area: BuildArea,
        heightmap,
        wall_top_y: int,
        wall_t: int,
        gate_w: int,
        wall_block: str,
        accent_block: str,
        found_block: str,
        light_block: str,
        window_block: str,
        tower_boxes: list,
        building_boxes: list,
        has_gate: bool = False,
    ) -> None:
        dx    = bx - ax
        dz    = bz - az
        steps = max(abs(dx), abs(dz))
        if steps == 0:
            return

        along_x   = abs(dx) >= abs(dz)
        gate_mid  = steps // 2
        gate_half = gate_w // 2
        light_props = {"hanging": "false"} if "lantern" in light_block else {}

        for step in range(0, steps + 1):
            t  = step / max(steps, 1)
            wx = int(ax + round(t * dx))
            wz = int(az + round(t * dz))

            if self._in_box(wx, wz, tower_boxes):
                continue
            if self._in_box(wx, wz, building_boxes):
                continue

            gy      = self._sample_ground_y(wx, wz, area, heightmap)
            is_gate = has_gate and abs(step - gate_mid) <= gate_half

            if is_gate:
                self._build_gate_column(
                    buffer,
                    wx, wz, gy, wall_top_y, wall_t, along_x,
                    wall_block, accent_block, found_block,
                    window_block, light_block,
                    is_centre=(step == gate_mid),
                    light_props=light_props,
                )
            else:
                self._build_wall_column(
                    buffer,
                    wx, wz, gy, wall_top_y, wall_t, along_x, step,
                    wall_block, accent_block, found_block,
                    light_block, light_props,
                )

    # ------------------------------------------------------------------
    # Normal wall column
    # ------------------------------------------------------------------

    def _build_wall_column(
        self,
        buffer: BlockBuffer,
        wx: int, wz: int, gy: int,
        wall_top_y: int, wall_t: int,
        along_x: bool, step: int,
        wall_block: str, accent_block: str, found_block: str,
        light_block: str, light_props: dict,
    ) -> None:
        for t in range(wall_t):
            ox = 0 if along_x else t
            oz = t if along_x else 0
            x, z = wx + ox, wz + oz
            for y in range(gy - _FOUND_DEPTH, gy):
                buffer.place(x, y, z, Block(found_block))
            for y in range(gy, wall_top_y):
                buffer.place(x, y, z, Block(wall_block))

        is_merlon = (step % 3 != 2)
        if is_merlon:
            buffer.place(wx, wall_top_y, wz, Block(accent_block))

        inner_t  = wall_t - 1
        ox_inner = 0 if along_x else inner_t
        oz_inner = inner_t if along_x else 0
        buffer.place(
            wx + ox_inner, wall_top_y, wz + oz_inner,
            Block(accent_block if is_merlon else wall_block),
        )

        wall_h_local = wall_top_y - gy
        if step % 8 in (0, 1) and wall_h_local > 1:
            butt_ox = (-1 if along_x else 0)
            butt_oz = (0 if along_x else -1)
            for dy in range(wall_h_local - 1):
                buffer.place(wx + butt_ox, gy + dy, wz + butt_oz, Block(wall_block))
            buffer.place(wx + butt_ox, wall_top_y - 1, wz + butt_oz, Block(accent_block))

        if step % 12 == 0 and is_merlon:
            buffer.place(wx, wall_top_y + 1, wz, Block(light_block, light_props))

    # ------------------------------------------------------------------
    # Gate arch column
    # ------------------------------------------------------------------

    def _build_gate_column(
        self,
        buffer: BlockBuffer,
        wx: int, wz: int, gy: int,
        wall_top_y: int, wall_t: int,
        along_x: bool,
        wall_block: str, accent_block: str, found_block: str,
        window_block: str, light_block: str,
        is_centre: bool, light_props: dict,
    ) -> None:
        gate_h     = 3
        wall_h_local = wall_top_y - gy

        for t in range(wall_t):
            ox  = 0 if along_x else t
            oz  = t if along_x else 0
            x, z = wx + ox, wz + oz
            for y in range(gy - _FOUND_DEPTH, gy):
                buffer.place(x, y, z, Block(found_block))
            for dy in range(max(0, wall_h_local)):
                y = gy + dy
                if dy < gate_h:
                    if t == 0:
                        buffer.place(x, y, z, Block(window_block))
                    else:
                        buffer.place(x, y, z, Block("minecraft:air"))
                elif dy == gate_h:
                    buffer.place(x, y, z, Block(accent_block))
                else:
                    buffer.place(x, y, z, Block(wall_block))

        buffer.place(wx, wall_top_y, wz, Block(accent_block))

        if is_centre:
            hang_props = {"hanging": "true"} if "lantern" in light_block else light_props
            buffer.place(wx, gy + gate_h - 1, wz, Block(light_block, hang_props))

        if not is_centre:
            inner_t  = wall_t - 1
            ox_inner = 0 if along_x else inner_t
            oz_inner = inner_t if along_x else 0
            buffer.place(
                wx + ox_inner, gy + gate_h, wz + oz_inner,
                Block("minecraft:wall_torch",
                      {"facing": "south" if along_x else "east"}),
            )
