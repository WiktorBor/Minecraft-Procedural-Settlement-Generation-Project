"""BlockBuffer — in-memory block placement accumulator."""
from __future__ import annotations

from gdpc import Block


class BlockBuffer:
    """
    Sparse in-memory buffer of world-coordinate block placements.

    Builders write into this buffer instead of calling editor.placeBlock()
    directly. StructurePlacer flushes it to Minecraft in one pass.
    """

    def __init__(self) -> None:
        self._blocks: dict[tuple[int, int, int], Block] = {}

    def place(self, x: int, y: int, z: int, block: Block) -> None:
        """Record a block at world position (x, y, z)."""
        self._blocks[(int(x), int(y), int(z))] = block

    def place_many(self, positions, block: Block) -> None:
        """Record the same block at multiple (x, y, z) positions."""
        for pos in positions:
            self._blocks[(int(pos[0]), int(pos[1]), int(pos[2]))] = block

    def merge(self, other: BlockBuffer) -> None:
        """Merge another buffer into this one. Later writes win on conflict."""
        self._blocks.update(other._blocks)

    def items(self):
        """Iterate over ((x, y, z), Block) pairs."""
        return self._blocks.items()

    def __len__(self) -> int:
        return len(self._blocks)
