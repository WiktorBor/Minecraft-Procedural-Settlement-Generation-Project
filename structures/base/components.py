"""
Shared primitive building-block functions for all structure builders.

Lives at structures/components.py so any structure (house, tower, farm, etc.)
can import from here without coupling to the house subpackage.

Usage
-----
Create a BuildContext with the editor, palette and desired rotation, then pass
it to any component function.  Rotation is applied via GDPC's native transform
system — all placement calls inside a pushTransform() block are automatically
rotated, so component functions themselves are rotation-unaware.

    ctx = BuildContext(editor, palette, rotation=90)
    with ctx.push():
        build_floor(ctx, x, y, z, width, depth)
        build_walls(ctx, x, y, z, width, height, depth)
        build_gabled_roof(ctx, x, y + height, z, width, depth)

All functions use placeBlock with an iterable of positions where possible,
which GDPC batches into a single HTTP request (see Editor.placeBlockGlobal).
The Editor must be constructed with buffering=True (done in main.py).
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

from gdpc import Block
from gdpc.editor import Editor
from gdpc.transform import rotatedBoxTransform
from gdpc.vector_tools import Box

from data.biome_palettes import BiomePalette, palette_get


# Block IDs that support the 'hanging' block state
_HANGING_CAPABLE: frozenset[str] = frozenset({
    "minecraft:lantern",
    "minecraft:soul_lantern",
    "minecraft:chain",
})


def place_light(
    editor: Editor,
    pos: tuple[int, int, int],
    block_id: str,
    hanging: bool = False,
) -> None:
    """
    Place a light block, applying 'hanging=true' only if the block supports it.
    Torches and similar blocks do not have a hanging property — this prevents
    the CommandSyntaxException that occurs when passing unsupported states.
    """
    if hanging and block_id in _HANGING_CAPABLE:
        editor.placeBlock(pos, Block(block_id, {"hanging": "true"}))
    else:
        editor.placeBlock(pos, Block(block_id))


# ---------------------------------------------------------------------------
# BuildContext
# ---------------------------------------------------------------------------

@dataclass
class BuildContext:
    """
    Shared build state passed to all component functions.

    Attributes
    ----------
    editor:   GDPC Editor instance.
    palette:  BiomePalette providing material block IDs.
    rotation: Clockwise rotation in degrees (0, 90, 180, 270).
              Applied via editor.pushTransform so components stay
              rotation-unaware.
    origin:   (x, y, z) pivot for the rotation transform.
              Set this to the structure's anchor corner before calling push().
    size:     (width, depth) of structure footprint.
    """
    editor:   Editor
    palette:  BiomePalette
    rotation: int = 0
    origin:   tuple[int, int, int] | None = None
    size:     tuple[int, int] = (1, 1)

    @contextmanager
    def push(self) -> Generator[None, None, None]:
        """
        Context manager that applies the rotation transform to the editor.

        All placeBlock calls made inside this block are automatically rotated.
        On exit the editor's transform is restored to its previous state.

        Component functions pass world-absolute coordinates to placeBlock.
        A rotatedBoxTransform adds the origin offset as a translation, which
        would double-offset world coords.  Skip the transform entirely when
        there is no rotation — world coordinates are already correct.
        """
        if self.rotation == 0:
            yield
            return

        steps = (self.rotation // 90) % 4
        ox, oy, oz = self.origin if self.origin else (0, 0, 0)

        box       = Box(offset=(ox, oy, oz), size=(self.size[0], 1, self.size[1]))
        transform = rotatedBoxTransform(box, steps)

        with self.editor.pushTransform(transform):
            yield

    def block(self, key: str, states: dict | None = None) -> Block:
        """Return a Block from the palette by key, with optional block states."""
        block_id = palette_get(self.palette, key, "minecraft:stone")
        return Block(block_id, states) if states else Block(block_id)

    def place(self, pos: tuple[int, int, int], key: str, states: dict | None = None) -> None:
        """Place a single palette block at pos."""
        self.editor.placeBlock(pos, self.block(key, states))

    def place_many(
        self,
        positions: list[tuple[int, int, int]],
        key: str,
        states: dict | None = None,
    ) -> None:
        """Place a palette block at multiple positions in a single call."""
        self.editor.placeBlock(positions, self.block(key, states))


# ---------------------------------------------------------------------------
# Primitive components — all take BuildContext as first argument
# ---------------------------------------------------------------------------

def build_layer(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    key: str = "floor",
) -> None:
    """Place a solid rectangle of palette blocks at a fixed Y level."""
    positions = [
        (x + dx, y, z + dz)
        for dx in range(width)
        for dz in range(depth)
    ]
    ctx.place_many(positions, key)


def build_floor(
    ctx: BuildContext, x: int, y: int, z: int, width: int, depth: int
) -> None:
    """Solid floor rectangle using the 'floor' palette key."""
    build_layer(ctx, x, y, z, width, depth, "floor")


def build_flat_roof(
    ctx: BuildContext, x: int, y: int, z: int, width: int, depth: int
) -> None:
    """Flat roof rectangle using the 'roof' palette key."""
    build_layer(ctx, x, y, z, width, depth, "roof")


def build_walls(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, height: int, depth: int,
) -> None:
    """
    Build hollow walls from y+1 to y+height (exclusive) using the 'wall' palette key.

    The floor is assumed to already be placed at y.
    Corner blocks are placed exactly once (no duplicate placements at intersections).
    """
    positions = []
    for dy in range(1, height):
        for dx in range(width):
            positions.append((x + dx, y + dy, z))
            positions.append((x + dx, y + dy, z + depth - 1))
        for dz in range(1, depth - 1):
            positions.append((x,             y + dy, z + dz))
            positions.append((x + width - 1, y + dy, z + dz))
    ctx.place_many(positions, "wall")


def build_foundation(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    depth_below: int = 3,
) -> None:
    """
    Solid foundation block from y downward using the 'foundation' palette key.
    Embeds the structure into uneven terrain naturally.
    """
    positions = [
        (x + dx, y - dy, z + dz)
        for dx in range(width)
        for dz in range(depth)
        for dy in range(1, depth_below + 1)
    ]
    ctx.place_many(positions, "foundation")


def build_gabled_roof(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
) -> None:
    """
    Build a gabled (pitched) roof.

    Uses palette keys:
      'roof'    — stair block for main slopes
      'accent'  — gable-end decoration
      'window'  — gable window block
      'floor'   — slab above gable windows

    Facing directions (east/west) are in local space — GDPC's pushTransform
    rotates them to world space automatically.
    """
    roof_mat  = ctx.palette.get("roof", "minecraft:spruce_stairs")
    roof_slab = (
        roof_mat.replace("_stairs", "_slab")
        if roof_mat.endswith("_stairs") else roof_mat
    )
    peak_height = width // 2

    for layer in range(peak_height):
        for dz in range(depth):
            ctx.editor.placeBlock(
                (x + layer,             y + layer, z + dz),
                Block(roof_mat, {"facing": "east"}),
            )
            ctx.editor.placeBlock(
                (x + width - 1 - layer, y + layer, z + dz),
                Block(roof_mat, {"facing": "west"}),
            )

    # Ridge cap for odd widths
    if width % 2 == 1:
        ridge_x   = x + width // 2
        ridge_y   = y + peak_height - 1
        positions = [(ridge_x, ridge_y, z + dz) for dz in range(depth)]
        ctx.editor.placeBlock(positions, Block(roof_slab, {"type": "top"}))

    # Gable-end decoration
    if width >= 5:
        center_x = x + width // 2
        accent   = ctx.palette.get("accent", "minecraft:cobblestone")
        positions = (
            [(dx, y,     z)             for dx in range(center_x - 2, center_x + 3)] +
            [(dx, y,     z + depth - 1) for dx in range(center_x - 2, center_x + 3)] +
            [(dx, y + 1, z)             for dx in (center_x - 1, center_x + 1)] +
            [(dx, y + 1, z + depth - 1) for dx in (center_x - 1, center_x + 1)]
        )
        ctx.editor.placeBlock(positions, Block(accent))

    # Gable windows
    window_mat = palette_get(ctx.palette, "window", "minecraft:glass_pane")
    if width >= 3 and peak_height >= 2:
        wx        = x + width // 2
        wy        = y + 1
        slab_y    = wy + 1
        floor_mat = ctx.palette.get("floor", "minecraft:spruce_planks")
        for face_z in (z, z + depth - 1):
            ctx.editor.placeBlock((wx, wy,     face_z), Block(window_mat))
            ctx.editor.placeBlock((wx, slab_y, face_z), Block(floor_mat))


def add_door(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int,
    facing: str = "south",
) -> None:
    """
    Place a two-block-tall door at the centre of the south face.
    Step block uses 'floor' palette key.
    """
    door_x     = x + width // 2
    door_block = "minecraft:spruce_door"
    ctx.place((door_x, y, z), "floor")
    ctx.editor.placeBlock(
        (door_x, y + 1, z),
        Block(door_block, {"facing": facing, "half": "lower", "hinge": "left"}),
    )
    ctx.editor.placeBlock(
        (door_x, y + 2, z),
        Block(door_block, {"facing": facing, "half": "upper", "hinge": "left"}),
    )


def add_windows(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    window_y_offset: int = 2,
) -> None:
    """
    Place windows on all faces wide enough (> 5 cells) using the 'window' palette key.
    """
    window_y  = y + window_y_offset
    positions = []
    if width > 5:
        positions += [
            (x + 1,         window_y, z),
            (x + width - 2, window_y, z),
            (x + 1,         window_y, z + depth - 1),
            (x + width - 2, window_y, z + depth - 1),
        ]
    if depth > 5:
        positions += [
            (x,             window_y, z + depth // 2),
            (x + width - 1, window_y, z + depth // 2),
        ]
    if positions:
        ctx.place_many(positions, "window")


def add_chimney(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
    building_height: int,
) -> None:
    """Chimney at back-right corner using the 'foundation' palette key."""
    chimney_x = x + width  - 2
    chimney_z = z + depth - 2
    positions = [(chimney_x, y + dy, chimney_z) for dy in range(building_height)]
    ctx.place_many(positions, "foundation")


def add_lanterns(
    ctx: BuildContext,
    x: int, y: int, z: int,
    width: int, depth: int,
) -> None:
    """Place lanterns at the four base corners using the 'light' palette key."""
    light     = palette_get(ctx.palette, "light", "minecraft:lantern")
    positions = [
        (x,             y, z),
        (x + width - 1, y, z),
        (x,             y, z + depth - 1),
        (x + width - 1, y, z + depth - 1),
    ]
    ctx.editor.placeBlock(positions, Block(light))