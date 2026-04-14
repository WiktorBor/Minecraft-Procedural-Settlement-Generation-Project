"""
structures/core/build_context.py
---------------------------------
Placement context shared by ALL structure builders.

BuildContext wraps a BlockBuffer and a palette. All block placement goes
through this context. There is NO rotation logic here — rotation is applied
once at the placement layer (structure_selector / structure_placer) by
transforming the finished BlockBuffer.

Each grammar builds fully axis-aligned (door always on local-north face,
etc.) and returns a BlockBuffer. The caller decides if and how to rotate it.

Usage
-----
    ctx = BuildContext(buffer=BlockBuffer(), palette=palette)
    build_floor(ctx, x, y, z, w, d)
    build_walls(ctx, x, y, z, w, h, d)
"""
from __future__ import annotations

from dataclasses import dataclass

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

    Attributes
    ----------
    buffer  : BlockBuffer that accumulates placements for this structure.
    palette : PaletteSystem providing material block IDs by semantic key.
    """
    buffer:  BlockBuffer
    palette: PaletteSystem

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
        x, y, z = pos
        self.buffer.place(x, y, z, self.block(key, states))

    def place_block(
        self,
        pos: tuple[int, int, int],
        block: Block,
    ) -> None:
        """Place a pre-built Block directly at pos."""
        x, y, z = pos
        self.buffer.place(x, y, z, block)

    def place_many(
        self,
        positions: list[tuple[int, int, int]],
        key: str,
        states: dict | None = None,
    ) -> None:
        """Place a palette block at every position in the list."""
        blk = self.block(key, states)
        for x, y, z in positions:
            self.buffer.place(x, y, z, blk)

    def place_light(
        self,
        pos: tuple[int, int, int],
        key: str = "light",
        hanging: bool = False,
    ) -> None:
        """
        Place a light block from the palette.

        If hanging=True and the block supports the 'hanging' state
        (lantern, soul lantern, chain), the state is applied automatically.
        """
        block_id = palette_get(self.palette, key, "minecraft:lantern")
        if hanging and block_id in HANGING_CAPABLE:
            blk = Block(block_id, {"hanging": "true"})
        else:
            blk = Block(block_id)
        x, y, z = pos
        self.buffer.place(x, y, z, blk)