"""
structures/base/build_context.py
---------------------------------
Rotation-aware placement context shared by ALL structure builders.

BuildContext wraps a BlockBuffer (not the Editor directly). All block
placement goes through this context so rotation transforms are applied
uniformly. StructurePlacer is responsible for flushing the buffer to
Minecraft.

Usage
-----
    ctx = BuildContext(buffer, palette, rotation=90, origin=(x, y, z), size=(w, d))
    with ctx.push():
        build_floor(ctx, x, y, z, w, d)
        build_walls(ctx, x, y, z, w, h, d)
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from world_interface.block_buffer import BlockBuffer


# ---------------------------------------------------------------------------
# Block IDs that support the 'hanging' block state
# ---------------------------------------------------------------------------

HANGING_CAPABLE: frozenset[str] = frozenset({
    "minecraft:lantern",
    "minecraft:soul_lantern",
    "minecraft:chain",
})


# ---------------------------------------------------------------------------
# BuildContext
# ---------------------------------------------------------------------------

@dataclass
class BuildContext:
    """
    Shared build state passed to all primitive and structure-specific functions.

    All block placement goes through this context so rotation transforms
    are applied uniformly. Create one per structure and pass it down.

    Rotation is applied as a pure coordinate transform — no editor dependency.

    Attributes
    ----------
    buffer   : BlockBuffer that accumulates placements for this structure.
    palette  : BiomePalette providing material block IDs by semantic key.
    rotation : Clockwise rotation in degrees — 0, 90, 180, or 270.
    origin   : (x, y, z) pivot for the rotation transform.
               Set to the structure's anchor corner before calling push().
    size     : (width, depth) of the structure footprint.
               Used together with origin to compute rotated coordinates.
    """
    buffer:   BlockBuffer
    palette:  PaletteSystem
    rotation: int                         = 0
    origin:   tuple[int, int, int] | None = None
    size:     tuple[int, int]             = (1, 1)

    # Active transform flag set by push()
    _transform_active: bool = field(default=False, init=False, repr=False)

    @contextmanager
    def push(self) -> Generator[None, None, None]:
        """
        Context manager that activates the rotation transform.

        All place* calls inside this block have their (x, z) coordinates
        rotated around `origin` by `rotation` degrees clockwise.
        When rotation == 0 no transform is applied.
        """
        if self.rotation == 0:
            yield
            return

        self._transform_active = True
        try:
            yield
        finally:
            self._transform_active = False

    def _apply_transform(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        """
        Apply the clockwise rotation transform to world coordinates.

        For a footprint anchored at origin (ox, oy, oz) with size (w, d):

            steps=1 (90° CW):  new_x = ox + (d-1) - (z-oz)
                                new_z = oz + (x-ox)
            steps=2 (180°):    new_x = ox + (w-1) - (x-ox)
                                new_z = oz + (d-1) - (z-oz)
            steps=3 (270° CW): new_x = ox + (z-oz)
                                new_z = oz + (w-1) - (x-ox)
        """
        if not self._transform_active or self.origin is None:
            return x, y, z

        steps     = (self.rotation // 90) % 4
        ox, _, oz = self.origin
        w, d      = self.size
        lx, lz    = x - ox, z - oz

        if steps == 1:
            return ox + (d - 1) - lz, y, oz + lx
        elif steps == 2:
            return ox + (w - 1) - lx, y, oz + (d - 1) - lz
        elif steps == 3:
            return ox + lz, y, oz + (w - 1) - lx
        return x, y, z

    # ------------------------------------------------------------------
    # Palette helpers
    # ------------------------------------------------------------------

    def block(self, key: str, states: dict | None = None) -> Block:
        """Return a Block from the palette by semantic key."""
        block_id = palette_get(self.palette, key, "minecraft:stone")
        return Block(block_id, states) if states else Block(block_id)

    # ------------------------------------------------------------------
    # Placement helpers
    # ------------------------------------------------------------------

    def place(
        self,
        pos: tuple[int, int, int],
        key: str,
        states: dict | None = None,
    ) -> None:
        """Place a single palette block at pos."""
        tx, ty, tz = self._apply_transform(*pos)
        self.buffer.place(tx, ty, tz, self.block(key, states))

    def place_block(
        self,
        pos: tuple[int, int, int],
        block: Block,
    ) -> None:
        """Place a pre-built Block at pos, rotating block state with the transform."""
        tx, ty, tz = self._apply_transform(*pos)
        if self._transform_active:
            steps = (self.rotation // 90) % 4
            if steps:
                block = block.transformed(steps, (False, False, False))
        self.buffer.place(tx, ty, tz, block)

    def place_many(
        self,
        positions: list[tuple[int, int, int]],
        key: str,
        states: dict | None = None,
    ) -> None:
        """Place a palette block at multiple positions."""
        blk = self.block(key, states)
        for pos in positions:
            tx, ty, tz = self._apply_transform(*pos)
            self.buffer.place(tx, ty, tz, blk)

    def place_light(
        self,
        pos: tuple[int, int, int],
        key: str = "light",
        hanging: bool = False,
    ) -> None:
        """Place a light block from the palette, respecting the hanging state."""
        block_id = palette_get(self.palette, key, "minecraft:lantern")
        if hanging and block_id in HANGING_CAPABLE:
            blk = Block(block_id, {"hanging": "true"})
        else:
            blk = Block(block_id)
        tx, ty, tz = self._apply_transform(*pos)
        self.buffer.place(tx, ty, tz, blk)
