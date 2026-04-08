"""StructurePlacer — the single point where blocks are written to Minecraft."""
from __future__ import annotations

import logging

from gdpc import Editor

from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)


class StructurePlacer:
    """
    Receives a BlockBuffer and flushes it to Minecraft via the Editor.

    This is the only place in the system that calls editor.placeBlock()
    or editor.flushBuffer(). All builders write to a BlockBuffer; this
    class handles the actual I/O.
    """

    def __init__(self, editor: Editor) -> None:
        self.editor = editor

    def place(self, buffer: BlockBuffer) -> None:
        """Place all blocks from the buffer and flush to Minecraft."""
        total = len(buffer)
        logger.info("Placing %d blocks...", total)
        for (x, y, z), block in buffer.items():
            self.editor.placeBlock((x, y, z), block)
        self.editor.flushBuffer()
        logger.info("  ✓ Flush complete.")
