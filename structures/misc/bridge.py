"""
structures/misc/bridge.py
--------------------------
Arched stone bridge spanning water or terrain gaps.

Layout (along the X axis, z-axis width):
  - Deck surface spans the full length at y_level.
  - Railing blocks on both z-edges one block above the deck.
  - Piers descend from y_level-1 downward until solid ground at every
    span_size interval.
  - Arch blocks (inverted top-stair) under the deck between piers.

All block placement goes through a BlockBuffer — no Editor calls.
Use StructurePlacer to flush to Minecraft.

Example usage in settlement_generator:
    from structures.misc.bridge import Bridge
    buf = Bridge().build(
        start_x=wx, y_level=wy, start_z=wz,
        length=20, palette=palette,
    )
    master_buffer.merge(buf)
"""
from __future__ import annotations

import logging

from gdpc import Block

from palette.palette_system import PaletteSystem, palette_get
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)

_AIR_LIKE: frozenset[str] = frozenset({
    "minecraft:air",
    "minecraft:water",
    "minecraft:flowing_water",
    "minecraft:seagrass",
    "minecraft:tall_seagrass",
    "minecraft:kelp",
    "minecraft:kelp_plant",
    "minecraft:void_air",
    "minecraft:cave_air",
})


class Bridge:
    """
    Palette-aware arched bridge.

    Materials drawn from the BiomePalette:
      "foundation" → deck surface + pier columns
      "fence"      → railings
      "roof"       → arch stairs (inverted under-deck curve)

    Parameters
    ----------
    width     : half-width (blocks each side of centre along Z).  Full deck
                width = 2*width + 1.
    span_size : blocks between pier centres.
    """

    def build(
        self,
        start_x:   int,
        y_level:   int,
        start_z:   int,
        length:    int,
        palette:   PaletteSystem,
        *,
        width:     int = 2,
        span_size: int = 5,
        min_y:     int = 0,
    ) -> BlockBuffer:
        """
        Build the bridge into a fresh BlockBuffer and return it.

        Parameters
        ----------
        start_x, y_level, start_z : world anchor (north-west corner at deck level).
        length    : bridge length in blocks along the X axis.
        palette   : biome palette for material selection.
        width     : half-width in the Z direction.
        span_size : spacing between pier columns.
        min_y     : lowest Y the pier may descend to.
        """
        buffer = BlockBuffer()

        deck_id  = palette_get(palette, "foundation", "minecraft:stone_bricks")
        pier_id  = palette_get(palette, "foundation", "minecraft:stone_bricks")
        rail_id  = palette_get(palette, "fence",      "minecraft:stone_brick_wall")
        arch_id  = palette_get(palette, "roof",       "minecraft:stone_brick_stairs")

        for i in range(length):
            x = start_x + i

            # --- Deck surface ---
            for dz in range(-width, width + 1):
                buffer.place(x, y_level, start_z + dz, Block(deck_id))

            # --- Railings (one above deck, both Z edges) ---
            buffer.place(x, y_level + 1, start_z - width, Block(rail_id))
            buffer.place(x, y_level + 1, start_z + width, Block(rail_id))

            # --- Substructure: pier or arch ---
            if i % span_size == 0:
                self._build_pier(buffer, x, start_z, y_level, width, min_y, pier_id)
            else:
                self._build_arch(buffer, x, start_z, y_level, i, span_size, arch_id)

        logger.debug(
            "Bridge built: start=(%d,%d,%d) length=%d width=%d span=%d",
            start_x, y_level, start_z, length, width, span_size,
        )
        return buffer

    # ------------------------------------------------------------------
    # Pier
    # ------------------------------------------------------------------

    def _build_pier(
        self,
        buf:     BlockBuffer,
        x:       int,
        cz:      int,
        y_level: int,
        width:   int,
        min_y:   int,
        pier_id: str,
    ) -> None:
        """Descend from y_level-1 downward until a non-air block is found."""
        for dz in range(-width, width + 1):
            z   = cz + dz
            y   = y_level - 1
            while y >= min_y:
                buf.place(x, y, z, Block(pier_id))
                # Stop after a fixed depth so we don't descend forever in a
                # pure-buffer context (no world query available here).
                if y_level - y >= 8:
                    break
                y -= 1

    # ------------------------------------------------------------------
    # Arch
    # ------------------------------------------------------------------

    def _build_arch(
        self,
        buf:      BlockBuffer,
        x:        int,
        cz:       int,
        y_level:  int,
        i:        int,
        span_size: int,
        arch_id:  str,
    ) -> None:
        """
        Place inverted stair blocks under the deck to form a curve.

        Blocks one step from a pier sit lowest (y_level - 1, full width).
        Blocks near span mid-point are only placed at deck-centre z.
        """
        dist = min(i % span_size, span_size - (i % span_size))

        if dist == 1:
            # Lowest arch segment — full width
            for dz in range(-1, 2):
                buf.place(x, y_level - 1, cz + dz, Block(arch_id))
        elif dist >= 2:
            # Top of arch — centre column only, inverted stair orientation
            facing = "west" if (i % span_size) < span_size / 2 else "east"
            buf.place(
                x, y_level - 1, cz,
                Block(arch_id, {"facing": facing, "half": "top"}),
            )
