"""
structures/base/build_context.py
---------------------------------
Rotation-aware placement context shared by ALL structure builders.

This is the single source of truth for:
  • BuildContext   — editor + palette + rotation transform
  • place_light    — handles hanging block-state safely

Every structure (house, tower, blacksmith, etc.) creates a BuildContext
and calls primitives through it.  Rotation is applied via GDPC's native
pushTransform — component functions pass world-absolute coordinates and
the transform handles the rest.

Usage
-----
    ctx = BuildContext(editor, palette, rotation=90, origin=(x, y, z), size=(w, d))
    with ctx.push():
        build_floor(ctx, x, y, z, w, d)
        build_walls(ctx, x, y, z, w, h, d)
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from gdpc import Block
from gdpc.editor import Editor
from gdpc.transform import rotatedBoxTransform
from gdpc.vector_tools import Box

from data.biome_palettes import BiomePalette, palette_get


# ---------------------------------------------------------------------------
# Block IDs that support the 'hanging' block state
# ---------------------------------------------------------------------------

HANGING_CAPABLE: frozenset[str] = frozenset({
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
    Place a light block, safely applying 'hanging=true' only when supported.

    Torches and similar blocks do not have a hanging property — passing
    unsupported states raises a CommandSyntaxException in GDPC.  This
    function guards against that.

    Args:
        editor:   GDPC Editor instance.
        pos:      (x, y, z) world position.
        block_id: Full Minecraft block ID, e.g. 'minecraft:lantern'.
        hanging:  Whether to attempt hanging=true (silently ignored for
                  block types that don't support it).
    """
    if hanging and block_id in HANGING_CAPABLE:
        editor.placeBlock(pos, Block(block_id, {"hanging": "true"}))
    else:
        editor.placeBlock(pos, Block(block_id))


# ---------------------------------------------------------------------------
# BuildContext
# ---------------------------------------------------------------------------

@dataclass
class BuildContext:
    """
    Shared build state passed to all primitive and structure-specific functions.

    All block placement goes through this context so rotation transforms
    are applied uniformly.  Create one per structure and pass it down.

    Attributes
    ----------
    editor   : GDPC Editor instance.
    palette  : BiomePalette providing material block IDs by semantic key.
    rotation : Clockwise rotation in degrees — 0, 90, 180, or 270.
               Applied via editor.pushTransform inside push().
    origin   : (x, y, z) pivot for the rotation transform.
               Set to the structure's anchor corner before calling push().
    size     : (width, depth) of the structure footprint.
               Used together with origin to compute the rotated bounding box.
    """
    editor:   Editor
    palette:  BiomePalette
    rotation: int                        = 0
    origin:   tuple[int, int, int] | None = None
    size:     tuple[int, int]            = (1, 1)

    @contextmanager
    def push(self) -> Generator[None, None, None]:
        """
        Context manager that applies the rotation transform to the editor.

        All placeBlock calls inside this block are automatically rotated
        around `origin`.  On exit the editor's transform is restored.

        When rotation == 0 the transform is skipped entirely — world
        coordinates are already correct and no offset would be applied.
        """
        if self.rotation == 0:
            yield
            return

        steps     = (self.rotation // 90) % 4
        ox, oy, oz = self.origin if self.origin else (0, 0, 0)
        box        = Box(offset=(ox, oy, oz), size=(self.size[0], 1, self.size[1]))
        transform  = rotatedBoxTransform(box, steps)

        with self.editor.pushTransform(transform):
            yield

    # ------------------------------------------------------------------
    # Palette helpers
    # ------------------------------------------------------------------

    def block(self, key: str, states: dict | None = None) -> Block:
        """Return a Block from the palette by semantic key."""
        block_id = palette_get(self.palette, key, "minecraft:stone")
        return Block(block_id, states) if states else Block(block_id)

    # ------------------------------------------------------------------
    # Placement helpers — thin wrappers so callers never touch editor directly
    # ------------------------------------------------------------------

    def place(
        self,
        pos: tuple[int, int, int],
        key: str,
        states: dict | None = None,
    ) -> None:
        """Place a single palette block at pos."""
        self.editor.placeBlock(pos, self.block(key, states))

    def place_block(
        self,
        pos: tuple[int, int, int],
        block: Block,
    ) -> None:
        """Place a pre-built Block at pos (for blocks that need explicit states)."""
        self.editor.placeBlock(pos, block)

    def place_many(
        self,
        positions: list[tuple[int, int, int]],
        key: str,
        states: dict | None = None,
    ) -> None:
        """Place a palette block at multiple positions in a single batched call."""
        self.editor.placeBlock(positions, self.block(key, states))

    def place_light(
        self,
        pos: tuple[int, int, int],
        key: str = "light",
        hanging: bool = False,
    ) -> None:
        """Place a light block from the palette, respecting the hanging state rule."""
        block_id = palette_get(self.palette, key, "minecraft:lantern")
        place_light(self.editor, pos, block_id, hanging=hanging)