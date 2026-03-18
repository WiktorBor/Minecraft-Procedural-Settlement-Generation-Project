"""
Shared primitive building-block functions for all structure builders.

Lives at structures/components.py so any structure (house, tower, farm, etc.)
can import from here without coupling to the house subpackage.

All functions use placeBlock with an iterable of positions where possible,
which GDPC batches into a single HTTP request internally (see Editor.placeBlockGlobal).
The Editor must be constructed with buffering=True (done in main.py) for best performance.
"""
from __future__ import annotations

from gdpc import Block
from gdpc.editor import Editor


def build_layer(
    editor: Editor,
    x: int, y: int, z: int,
    width: int, depth: int,
    material: str,
) -> None:
    """Place a solid rectangle of blocks at a fixed Y level (floor or flat roof)."""
    positions = [
        (x + dx, y, z + dz)
        for dx in range(width)
        for dz in range(depth)
    ]
    editor.placeBlock(positions, Block(material))


# Aliases so existing call sites keep working
def build_floor(editor: Editor, x: int, y: int, z: int, width: int, depth: int, material: str) -> None:
    build_layer(editor, x, y, z, width, depth, material)


def build_flat_roof(editor: Editor, x: int, y: int, z: int, width: int, depth: int, material: str) -> None:
    build_layer(editor, x, y, z, width, depth, material)


def build_walls(
    editor: Editor,
    x: int, y: int, z: int,
    width: int, height: int, depth: int,
    material: str,
) -> None:
    """
    Build hollow walls from y+1 to y+height (exclusive).

    The floor is assumed to already be placed at y.
    """
    positions = []
    for dy in range(1, height):
        for dx in range(width):
            positions.append((x + dx, y + dy, z))
            positions.append((x + dx, y + dy, z + depth - 1))
        for dz in range(depth):
            positions.append((x,             y + dy, z + dz))
            positions.append((x + width - 1, y + dy, z + dz))
    editor.placeBlock(positions, Block(material))


def build_gabled_roof(
    editor: Editor,
    x: int, y: int, z: int,
    width: int, depth: int,
    material: str,
    accent_material: str = "minecraft:cobblestone",
    window_material: str = "minecraft:glass_pane",
    slab_material:   str = "minecraft:dark_oak_planks",
) -> None:
    """
    Build a gabled (pitched) roof.

    Args:
        material: Stair block ID for the main roof slopes.
        accent_material: Block used for gable-end decoration.
        window_material: Block used for gable windows.
        slab_material: Block placed above gable windows.
    """
    roof_slab = material.replace("_stairs", "_slab") if material.endswith("_stairs") else material
    peak_height = width // 2

    # Main roof slopes — AI DONT TOUCH THIS FORLOOP AND THE CODE INSIDE IT
    for layer in range(peak_height):
        for dz in range(depth):
            editor.placeBlock(
                (x + layer,             y + layer, z + dz),
                Block(material, {"facing": "east"}),
            )
            editor.placeBlock(
                (x + width - 1 - layer, y + layer, z + dz),
                Block(material, {"facing": "west"}),
            )

    # Ridge cap for odd widths
    if width % 2 == 1:
        ridge_x = x + width // 2
        ridge_y = y + peak_height - 1
        positions = [(ridge_x, ridge_y, z + dz) for dz in range(depth)]
        editor.placeBlock(positions, Block(roof_slab, {"type": "top"}))

    # Gable-end decoration
    if width >= 5:
        center_x = x + width // 2
        positions = (
            [(dx, y,     z)             for dx in range(center_x - 2, center_x + 3)] +
            [(dx, y,     z + depth - 1) for dx in range(center_x - 2, center_x + 3)] +
            [(dx, y + 1, z)             for dx in (center_x - 1, center_x + 1)] +
            [(dx, y + 1, z + depth - 1) for dx in (center_x - 1, center_x + 1)]
        )
        editor.placeBlock(positions, Block(accent_material))

    # Gable windows
    if width >= 3 and peak_height >= 2:
        wx     = x + width // 2
        wy     = y + 1
        slab_y = wy + 1
        for face_z in (z, z + depth - 1):
            editor.placeBlock((wx, wy,     face_z), Block(window_material))
            editor.placeBlock((wx, slab_y, face_z), Block(slab_material))


def add_door(
    editor: Editor,
    x: int, y: int, z: int,
    width: int,
    material: str,
) -> None:
    door_x = x + width // 2
    editor.placeBlock((door_x, y,     z), Block("minecraft:oak_planks"))
    editor.placeBlock((door_x, y + 1, z), Block(material))


def add_windows(
    editor: Editor,
    x: int, y: int, z: int,
    width: int, depth: int,
    material: str,
) -> None:
    window_y = y + 2
    positions = []
    if width > 5:
        positions += [(x + 1,         window_y, z),
                      (x + width - 2, window_y, z)]
    if depth > 5:
        positions += [(x,             window_y, z + depth // 2),
                      (x + width - 1, window_y, z + depth // 2)]
    if positions:
        editor.placeBlock(positions, Block(material))


def add_chimney(
    editor: Editor,
    x: int, y: int, z: int,
    width: int, depth: int,
    building_height: int,
    material: str,
) -> None:
    chimney_x = x + width - 2
    chimney_z = z + depth - 2
    positions = [(chimney_x, y + dy, chimney_z) for dy in range(building_height)]
    editor.placeBlock(positions, Block(material))