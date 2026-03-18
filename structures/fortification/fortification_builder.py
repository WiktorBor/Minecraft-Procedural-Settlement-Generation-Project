from __future__ import annotations

import logging
from typing import Iterable

from gdpc import Block
from gdpc.editor import Editor
import gdpc.geometry as geo

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette, palette_get
from data.build_area import BuildArea
from data.configurations import SettlementConfig
from data.settlement_entities import Building

logger = logging.getLogger(__name__)


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
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette,
        config: SettlementConfig,
    ) -> None:
        self.editor   = editor
        self.analysis = analysis
        self.palette  = palette
        self.config   = config

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, buildings: Iterable[Building] | None = None) -> None:
        """
        Place the full fortification.

        Args:
            buildings: Optional iterable of already-placed Building objects.
                       The wall will never overwrite any building footprint.
        """
        area      = self.analysis.best_area
        heightmap = self.analysis.heightmap_ground
        cfg       = self.config

        tw  = cfg.tower_width
        th  = cfg.tower_height
        wh  = cfg.wall_height
        wt  = cfg.wall_thickness
        gw  = getattr(cfg, "gate_width", 4)

        wall_block   = self.palette["wall"]
        accent_block = self.palette["accent"]
        found_block  = self.palette["foundation"]
        light_block  = palette_get(self.palette, "light",  "minecraft:lantern")
        window_block = palette_get(self.palette, "window", "minecraft:iron_bars")
        door_block   = palette_get(self.palette, "door",   "minecraft:oak_door")
        slab_block   = palette_get(self.palette, "slab",   "minecraft:cobblestone_slab")

        corners = self._corner_positions(area, tw)

        # Tower bounding boxes for wall collision checks
        tower_boxes = [
            (cx, cz, cx + tw - 1, cz + tw - 1)
            for cx, cz in corners
        ]

        # Building footprints — expand by 1 block buffer
        building_boxes: list[tuple[int,int,int,int]] = []
        if buildings:
            for b in buildings:
                building_boxes.append((
                    b.x - 1, b.z - 1,
                    b.x + b.width, b.z + b.depth,
                ))

        # --- Corner towers ---
        # Towers sit outside best_area so world_to_index will raise ValueError.
        # Clamp the lookup to the nearest best_area edge for a sensible ground height.
        from structures.tower.tower_builder import TowerBuilder
        tower_builder = TowerBuilder(self.editor, self.palette, height=th, width=tw)
        for cx, cz in corners:
            li = max(0, min(heightmap.shape[0] - 1, cx - area.x_from))
            lj = max(0, min(heightmap.shape[1] - 1, cz - area.z_from))
            cy = int(heightmap[li, lj])
            tower_builder.build_at(cx, cy, cz)

        # --- Wall segments ---
        # Each wall runs at the tower midline and spans exactly the best_area side.
        # South wall gets the gate.
        wall_sides = [
            ("north", False),
            ("south", True),
            ("east",  False),
            ("west",  False),
        ]

        for side, has_gate in wall_sides:
            sx, sz, ex, ez = self._wall_midline(area, side, tw)
            self._build_wall_segment(
                sx, sz, ex, ez,
                area, heightmap,
                wh, wt, gw,
                wall_block, accent_block, found_block,
                light_block, window_block, slab_block,
                tower_boxes=tower_boxes,
                building_boxes=building_boxes,
                has_gate=has_gate,
            )

        logger.info("Fortification: 4 towers + 4 walls + 1 gate.")

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _corner_positions(area: BuildArea, tw: int) -> list[tuple[int, int]]:
        """
        [NW, NE, SW, SE] tower origins positioned so the tower inner corner
        is exactly flush with the best_area corner.

        Tower NW origin is at (area.x_from - tw, area.z_from - tw).
        The inner corner of that tower (x + tw-1, z + tw-1) = (area.x_from - 1, area.z_from - 1)
        which is exactly adjacent to the area corner — no gap, no overlap.
        """
        return [
            (area.x_from - tw,  area.z_from - tw),   # NW
            (area.x_to   + 1,   area.z_from - tw),   # NE
            (area.x_from - tw,  area.z_to   + 1),    # SW
            (area.x_to   + 1,   area.z_to   + 1),    # SE
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

        The wall runs at the midpoint of the tower face (tower_origin + tw//2),
        and spans exactly the length of the corresponding best_area side.

        side: "north" | "south" | "east" | "west"
        """
        mid = tw // 2   # offset from tower origin to tower midline

        if side == "north":
            # Wall runs along X at z = area.z_from - mid - 1
            # spans x from area.x_from to area.x_to
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
    def _in_box(
        wx: int, wz: int,
        boxes: list[tuple[int,int,int,int]],
        thickness: int = 0,
    ) -> bool:
        """Return True if (wx, wz) falls inside any box (with optional thickness padding)."""
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
        ax: int, az: int,
        bx: int, bz: int,
        area: BuildArea,
        heightmap,
        wall_h: int,
        wall_t: int,
        gate_w: int,
        wall_block: str,
        accent_block: str,
        found_block: str,
        light_block: str,
        window_block: str,
        slab_block: str,
        tower_boxes: list,
        building_boxes: list,
        has_gate: bool = False,
    ) -> None:
        dx = bx - ax
        dz = bz - az
        steps = max(abs(dx), abs(dz))
        if steps == 0:
            return

        along_x    = abs(dx) >= abs(dz)
        gate_mid   = steps // 2
        gate_half  = gate_w // 2
        light_props = {"hanging": "false"} if "lantern" in light_block else {}

        for step in range(0, steps + 1):
            t  = step / max(steps, 1)
            wx = int(ax + round(t * dx))
            wz = int(az + round(t * dz))

            # Skip if this column is inside a tower footprint
            if self._in_box(wx, wz, tower_boxes):
                continue

            # Skip if this column overlaps a building (with 1-block buffer)
            if self._in_box(wx, wz, building_boxes):
                continue

            # Clamp to nearest best_area edge for height — wall may be just outside
            li = max(0, min(heightmap.shape[0] - 1, wx - area.x_from))
            lj = max(0, min(heightmap.shape[1] - 1, wz - area.z_from))
            gy = int(heightmap[li, lj])

            is_gate = has_gate and abs(step - gate_mid) <= gate_half

            if is_gate:
                self._build_gate_column(
                    wx, wz, gy, wall_h, wall_t, along_x,
                    wall_block, accent_block, found_block,
                    window_block, slab_block, light_block,
                    is_centre=(step == gate_mid),
                    light_props=light_props,
                )
            else:
                self._build_wall_column(
                    wx, wz, gy, wall_h, wall_t, along_x, step,
                    wall_block, accent_block, found_block,
                    light_block, light_props,
                )

    # ------------------------------------------------------------------
    # Normal wall column
    # ------------------------------------------------------------------

    def _build_wall_column(
        self,
        wx: int, wz: int, gy: int,
        wall_h: int, wall_t: int,
        along_x: bool, step: int,
        wall_block: str, accent_block: str, found_block: str,
        light_block: str, light_props: dict,
    ) -> None:
        # Foundation 1 below ground
        for t in range(wall_t):
            ox = 0 if along_x else t
            oz = t if along_x else 0
            self.editor.placeBlock((wx + ox, gy - 1, wz + oz), Block(found_block))

        # Solid wall body (all thickness layers)
        for dy in range(wall_h):
            y = gy + dy
            for t in range(wall_t):
                ox = 0 if along_x else t
                oz = t if along_x else 0
                self.editor.placeBlock((wx + ox, y, wz + oz), Block(wall_block))

        top_y = gy + wall_h

        # Proper battlements: 2-wide merlon then 1-wide gap (pattern repeats every 3)
        # step % 3 == 0 or 1 → merlon, step % 3 == 2 → gap
        is_merlon = (step % 3 != 2)
        if is_merlon:
            self.editor.placeBlock((wx, top_y, wz), Block(accent_block))

        # Walkway slab on inner face of wall top (only on inner thickness layer)
        inner_t = wall_t - 1
        ox_inner = 0 if along_x else inner_t
        oz_inner = inner_t if along_x else 0
        self.editor.placeBlock(
            (wx + ox_inner, top_y, wz + oz_inner),
            Block(accent_block if is_merlon else wall_block))

        # Buttress: protruding 1 block outward every 8 steps, 2 blocks wide
        # Buttress sticks out on the outer face (t=0 direction)
        if step % 8 in (0, 1):
            butt_ox = (-1 if along_x else 0)
            butt_oz = (0 if along_x else -1)
            for dy in range(wall_h - 1):  # slightly shorter than wall
                self.editor.placeBlock(
                    (wx + butt_ox, gy + dy, wz + butt_oz),
                    Block(wall_block))
            # Buttress cap (slab)
            self.editor.placeBlock(
                (wx + butt_ox, gy + wall_h - 1, wz + butt_oz),
                Block(accent_block))

        # Lantern on a merlon every 12 steps
        if step % 12 == 0 and is_merlon:
            self.editor.placeBlock(
                (wx, top_y + 1, wz), Block(light_block, light_props))

    # ------------------------------------------------------------------
    # Gate arch column
    # ------------------------------------------------------------------

    def _build_gate_column(
        self,
        wx: int, wz: int, gy: int,
        wall_h: int, wall_t: int,
        along_x: bool,
        wall_block: str, accent_block: str, found_block: str,
        window_block: str, slab_block: str, light_block: str,
        is_centre: bool, light_props: dict,
    ) -> None:
        """
        Gate arch column.

        Layout (from bottom up):
          gy+0 .. gy+2  : open passage (air inside, iron bars on outer face)
          gy+3          : arch keystone row — accent block forms the lintel
          gy+4 .. top   : solid wall above arch
          top           : merlon cap

        The accent block forms a visible arch frame on the outer face.
        A hanging lantern drops from the keystone centre.
        Torches are placed on the inner arch jambs for warmth.
        """
        gate_h = 3   # clear opening height

        # Foundation
        for t in range(wall_t):
            ox = 0 if along_x else t
            oz = t if along_x else 0
            self.editor.placeBlock((wx + ox, gy - 1, wz + oz), Block(found_block))

        for dy in range(wall_h):
            y = gy + dy
            for t in range(wall_t):
                ox = 0 if along_x else t
                oz = t if along_x else 0
                wx_ = wx + ox
                wz_ = wz + oz

                if dy < gate_h:
                    if t == 0:
                        # Outer face: iron bar portcullis in the opening
                        self.editor.placeBlock((wx_, y, wz_), Block(window_block))
                    else:
                        self.editor.placeBlock((wx_, y, wz_), Block("minecraft:air"))

                elif dy == gate_h:
                    # Arch lintel row — accent block on all faces for a clear frame
                    self.editor.placeBlock((wx_, y, wz_), Block(accent_block))

                else:
                    self.editor.placeBlock((wx_, y, wz_), Block(wall_block))

        # Merlon cap on top
        top_y = gy + wall_h
        self.editor.placeBlock((wx, top_y, wz), Block(accent_block))

        # Hanging lantern at keystone centre
        if is_centre:
            hang_props = {"hanging": "true"} if "lantern" in light_block else light_props
            self.editor.placeBlock(
                (wx, gy + gate_h - 1, wz), Block(light_block, hang_props))

        # Torch on inner arch jamb (the block just inside the passage at gate_h-1)
        if not is_centre:
            inner_t = wall_t - 1
            ox_inner = 0 if along_x else inner_t
            oz_inner = inner_t if along_x else 0
            self.editor.placeBlock(
                (wx + ox_inner, gy + gate_h, wz + oz_inner),
                Block("minecraft:wall_torch",
                      {"facing": "south" if along_x else "east"}))