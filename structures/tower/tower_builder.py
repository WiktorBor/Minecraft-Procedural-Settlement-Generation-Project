from __future__ import annotations

import logging
import random

from gdpc import Block
from gdpc.editor import Editor
import gdpc.geometry as geo

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot

logger = logging.getLogger(__name__)


class TowerBuilder:
    """
    Medieval corner tower with:
    - Hollow walls, embedded foundation
    - Pyramid / hipped roof built from stair layers
    - Proper crenellated parapet (full merlons, not single blocks)
    - Arrow-slit windows at two heights
    - Banner/flag on top
    - Palette-driven throughout
    """

    def __init__(
        self,
        editor: Editor,
        palette: BiomePalette,
        height: int = 8,
        width: int = 5,
    ) -> None:
        self.editor  = editor
        self.palette = palette
        self.height  = height
        self.width   = width

    def build(self, plot: Plot) -> None:
        self._build(plot.x, plot.y, plot.z)

    def build_at(self, x: int, y: int, z: int) -> None:
        self._build(x, y, z)

    def _build(self, x: int, y: int, z: int) -> None:
        w = self.width
        h = self.height

        wall_block   = self.palette["wall"]
        floor_block  = self.palette["floor"]
        accent_block = self.palette["accent"]
        found_block  = self.palette["foundation"]
        roof_block   = self.palette["roof"]
        light_block  = palette_get(self.palette, "light",     "minecraft:lantern")
        window_block = palette_get(self.palette, "window",    "minecraft:iron_bars")
        door_block   = palette_get(self.palette, "door",      "minecraft:oak_door")
        slab_block   = palette_get(self.palette, "roof_slab", "minecraft:cobblestone_slab")

        light_props = {"hanging": "false"} if "lantern" in light_block else {}

        # Foundation
        geo.placeCuboid(
            self.editor,
            (x, y - 2, z), (x + w - 1, y - 1, z + w - 1),
            Block(found_block),
        )

        # Hollow body
        geo.placeCuboidHollow(
            self.editor,
            (x, y, z), (x + w - 1, y + h - 1, z + w - 1),
            Block(wall_block),
        )

        # Floors
        geo.placeCuboid(
            self.editor,
            (x, y, z), (x + w - 1, y, z + w - 1),
            Block(floor_block),
        )
        mid_y = y + h // 2
        geo.placeCuboid(
            self.editor,
            (x + 1, mid_y, z + 1), (x + w - 2, mid_y, z + w - 2),
            Block(floor_block),
        )

        # Pyramid roof (stair layers stepping inward)
        roof_base = y + h
        peak      = w // 2
        for layer in range(peak):
            rx0 = x + layer
            rz0 = z + layer
            rx1 = x + w - 1 - layer
            rz1 = z + w - 1 - layer
            if rx0 > rx1 or rz0 > rz1:
                break
            ry = roof_base + layer
            for rx in range(rx0, rx1 + 1):
                self.editor.placeBlock(
                    (rx, ry, rz0), Block(roof_block, {"facing": "south"})
                )
                self.editor.placeBlock(
                    (rx, ry, rz1), Block(roof_block, {"facing": "north"})
                )
            for rz in range(rz0 + 1, rz1):
                self.editor.placeBlock(
                    (rx0, ry, rz), Block(roof_block, {"facing": "east"})
                )
                self.editor.placeBlock(
                    (rx1, ry, rz), Block(roof_block, {"facing": "west"})
                )

        # Flat cap at peak if width is odd
        if w % 2 == 1:
            mid = w // 2
            self.editor.placeBlock(
                (x + mid, roof_base + peak, z + mid),
                Block(slab_block, {"type": "top"}),
            )

        # Parapet below roof: solid course + proper merlons
        parapet_y = roof_base
        geo.placeCuboidWireframe(
            self.editor,
            (x, parapet_y - 1, z), (x + w - 1, parapet_y - 1, z + w - 1),
            Block(wall_block),
        )
        for i in range(w):
            for j in range(w):
                on_edge = (i == 0 or i == w - 1 or j == 0 or j == w - 1)
                if on_edge and i % 3 != 2 and j % 3 != 2:
                    self.editor.placeBlock(
                        (x + i, parapet_y, z + j), Block(accent_block)
                    )

        # Corner lanterns
        for lx, lz in [
            (x,     z    ),
            (x+w-1, z    ),
            (x,     z+w-1),
            (x+w-1, z+w-1),
        ]:
            self.editor.placeBlock((lx, parapet_y + 1, lz), Block(light_block, light_props))

        # Arrow slits at lower and upper height
        door_x = x + w // 2
        for slit_y in [y + h // 3, y + (h * 2) // 3]:
            for wx_, wz_ in [
                (door_x,    z        ),
                (door_x,    z + w - 1),
                (x,         z + w // 2),
                (x + w - 1, z + w // 2),
            ]:
                self.editor.placeBlock((wx_, slit_y, wz_), Block(window_block))

        # Door
        self.editor.placeBlock(
            (door_x, y + 1, z),
            Block(door_block, {"facing": "south", "half": "lower", "hinge": "left"}),
        )
        self.editor.placeBlock(
            (door_x, y + 2, z),
            Block(door_block, {"facing": "south", "half": "upper", "hinge": "left"}),
        )

        # Ladder on back wall
        geo.placeLine(
            self.editor,
            (door_x, y + 1, z + w - 1),
            (door_x, y + h - 1, z + w - 1),
            Block("minecraft:ladder", {"facing": "south"}),
        )

        # Banner/flag on roof peak
        flag_y  = roof_base + peak + (1 if w % 2 == 1 else 0)
        color   = random.choice(["purple", "blue", "red", "white"])
        self.editor.placeBlock(
            (x + w // 2, flag_y, z + w // 2),
            Block(f"minecraft:{color}_banner", {"rotation": "0"}),
        )

        logger.debug("Tower built at (%d,%d,%d) h=%d w=%d.", x, y, z, h, w)