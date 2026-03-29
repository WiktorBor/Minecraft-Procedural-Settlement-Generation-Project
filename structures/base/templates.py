"""
structures/templates.py
-----------------------
High-level structure templates built on top of structures/components.py.

Each template class exposes a single public method:

    build(editor, x, y, z, w, d, palette) -> None

Templates use BuildContext and the primitive component functions from
components.py. All block placement goes through BuildContext so rotation
transforms are applied automatically.

Missing functions
-----------------
add_furniture(), add_lighting(), and build_forge() are referenced by several
templates but not yet implemented. Each call site is marked with a TODO so
they can be filled in incrementally without the templates crashing.
"""
from __future__ import annotations

import math
import random

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette
from structures.base.components import (
    BuildContext,
    add_chimney,
    add_door,
    add_lanterns,
    add_windows,
    build_floor,
    build_foundation,
    build_gabled_roof,
    build_walls,
)


# ---------------------------------------------------------------------------
# Stub helpers — implement these when the feature is ready
# ---------------------------------------------------------------------------

def _add_furniture(editor: Editor, x: int, y: int, z: int, w: int, d: int, set_name: str = "basic_living") -> None:
    """TODO: place interior furniture set."""
    pass


def _add_lighting(editor: Editor, x: int, y: int, z: int, w: int, d: int, height: int, style: str = "lantern") -> None:
    """TODO: place interior/exterior lighting."""
    pass


def _build_forge(editor: Editor, x: int, y: int, z: int, palette: BiomePalette) -> None:
    """TODO: place blacksmith forge (furnaces, anvil, etc.)."""
    pass


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

class TowerHouseTemplate:
    """
    Complex medieval structure with a main living wing and an attached stone tower.
    """

    def build(
        self,
        editor: Editor,
        x: int, y: int, z: int,
        w: int, d: int,
        palette: BiomePalette,
    ) -> None:
        ctx = BuildContext(editor, palette, origin=(x, y, z), size=(w, d))

        tw = min(4, w // 2) if w > 4 else 2
        td = min(4, d // 2) if d > 4 else 2
        hw = w - tw

        with ctx.push():
            if hw > 1:
                build_foundation(ctx, x, y, z, w, d)
                build_walls(ctx, x + tw, y, z, hw, 5, d)
                build_floor(ctx, x + tw, y, z, hw, d)
                build_gabled_roof(ctx, x + tw, y + 5, z, hw, d)
                add_windows(ctx, x + tw, y, z, hw, d)
                add_door(ctx, x + tw, y, z, hw)
                _add_furniture(editor, x + tw, y, z, hw, d, set_name="basic_living")
                _add_lighting(editor, x + tw, y, z, hw, d, height=4, style="lantern")

            tower_h = 9
            build_foundation(ctx, x, y, z, tw, td)
            build_walls(ctx, x, y, z, tw, tower_h, td)
            build_floor(ctx, x, y, z, tw, td)
            build_floor(ctx, x, y + tower_h, z, tw, td)
            add_door(ctx, x, y, z, tw)
            add_windows(ctx, x, y + 5, z, tw, td)
            _add_lighting(editor, x, y, z, tw, td, height=7, style="fancy")

            if hw > 2:
                add_chimney(ctx, x + tw + (hw // 2), y, z + d - 1, tw, td, 8)


class SimpleCottageTemplate:
    """Standard 1-room rectangular house for smaller plots or rural districts."""

    def build(
        self,
        editor: Editor,
        x: int, y: int, z: int,
        w: int, d: int,
        palette: BiomePalette,
    ) -> None:
        if w < 5 or d < 5:
            return

        ctx    = BuildContext(editor, palette, origin=(x, y, z), size=(w, d))
        wall_h = 4

        with ctx.push():
            build_foundation(ctx, x, y, z, w, d)
            build_floor(ctx, x, y, z, w, d)
            build_walls(ctx, x, y, z, w, wall_h, d)
            build_gabled_roof(ctx, x, y + wall_h, z, w, d)
            add_door(ctx, x, y, z, w)
            add_windows(ctx, x, y, z, w, d)
            _add_furniture(editor, x, y, z, w, d, set_name="basic_living")
            _add_lighting(editor, x, y, z, w, d, height=4, style="fancy")
            add_chimney(ctx, x, y, z, w, d, wall_h + 2)


class BlacksmithTemplate:
    """Industrial building with an open-air forge and a stone living area."""

    def build(
        self,
        editor: Editor,
        x: int, y: int, z: int,
        w: int, d: int,
        palette: BiomePalette,
    ) -> None:
        forge_d = max(2, d // 3)
        house_d = d - forge_d
        house_z = z + forge_d

        if house_d < 3:
            return

        ctx = BuildContext(editor, palette, origin=(x, y, z), size=(w, d))

        with ctx.push():
            build_foundation(ctx, x, y, z, w, d)
            _build_forge(editor, x + (w // 2) - 1, y, z, palette)

            build_floor(ctx, x, y, house_z, w, house_d)
            build_walls(ctx, x, y, house_z, w, 4, house_d)
            build_gabled_roof(ctx, x, y + 4, house_z, w, house_d)
            add_door(ctx, x, y, house_z, w)
            _add_furniture(editor, x, y, house_z, w, house_d, set_name="blacksmith_workshop")
            _add_lighting(editor, x, y, house_z, w, house_d, height=3, style="industrial")


class SquareCentreTemplate:
    """Grand stone plaza that adapts its radius to the provided plot size."""

    def build(
        self,
        editor: Editor,
        x: int, y: int, z: int,
        w: int, d: int,
        palette: BiomePalette,
    ) -> None:
        radius = min(w, d) // 2

        if radius < 5:
            self._build_simple_paving(editor, x, y, z, w, d)
            return

        stone_mix = [
            "minecraft:stone_bricks",
            "minecraft:cobblestone",
            "minecraft:andesite",
        ]

        for ix in range(x - radius, x + radius + 1):
            for iz in range(z - radius, z + radius + 1):
                dist = math.sqrt((ix - x) ** 2 + (iz - z) ** 2)
                if dist <= radius:
                    b_type = stone_mix[(ix ^ iz) % len(stone_mix)]
                    editor.placeBlock((ix, y, iz), Block(b_type))
                    for iy in range(y + 1, y + 20):
                        editor.placeBlock((ix, iy, iz), Block("minecraft:air"))

        self._build_large_stepped_basin(editor, x, y, z, radius)

    def _build_large_stepped_basin(
        self, editor: Editor, x: int, y: int, z: int, radius: int
    ) -> None:
        r1 = radius - 1
        r2 = int(r1 * 0.7)
        r3 = int(r1 * 0.4)

        for r, h_offset, block in [
            (r1, 1, "smooth_stone"),
            (r2, 2, "smooth_stone"),
            (r3, 3, "smooth_stone"),
        ]:
            if r < 1:
                continue
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if dx ** 2 + dz ** 2 <= r ** 2:
                        editor.placeBlock(
                            (x + dx, y + h_offset, z + dz),
                            Block(f"minecraft:{block}"),
                        )

        basin_r = max(1, int(r3 * 0.8))
        for dx in range(-basin_r, basin_r + 1):
            for dz in range(-basin_r, basin_r + 1):
                if dx ** 2 + dz ** 2 <= basin_r ** 2:
                    editor.placeBlock((x + dx, y + 3, z + dz), Block("minecraft:water"))
                    editor.placeBlock((x + dx, y + 2, z + dz), Block("minecraft:sea_lantern"))

    def _build_simple_paving(
        self, editor: Editor, x: int, y: int, z: int, w: int, d: int
    ) -> None:
        for ix in range(x - w // 2, x + w // 2):
            for iz in range(z - d // 2, z + d // 2):
                editor.placeBlock((ix, y, iz), Block("minecraft:stone_bricks"))


class MarketStallTemplate:
    """Self-adjusting market stall."""

    def build(
        self,
        editor: Editor,
        x: int, y: int, z: int,
        w: int, d: int,
        palette: BiomePalette,
    ) -> None:
        color = random.choice(["red", "white", "yellow", "blue"])
        wool  = f"minecraft:{color}_wool"

        px = max(1, w // 2)
        pz = max(1, d // 2)

        for iy in range(y + 1, y + 4):
            editor.placeBlock((x - px, iy, z - pz), Block("minecraft:spruce_fence"))
            editor.placeBlock((x + px, iy, z - pz), Block("minecraft:spruce_fence"))

        for ix in range(x - px, x + px + 1):
            for iz in range(z - pz, z + pz + 1):
                editor.placeBlock((ix, y + 4, iz), Block(wool))