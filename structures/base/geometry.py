"""
structures/core/geometry.py
-----------------------------
Low-level geometry helpers that write through a BuildContext.

These functions deal in raw Block objects (not palette keys) and are
used when a builder needs to fill or outline a volume with a specific
block it has already resolved — e.g. a themed wall material or a
Block with custom states.

All writes go through ctx.place_block so the buffer is always the
single write target, consistent with every other primitive in core.

Functions
---------
  fill_cuboid           — solid rectangular volume
  fill_cuboid_wireframe — edges only (wireframe) of a rectangular volume
  fill_line             — axis-aligned line between two points
"""
from __future__ import annotations

from gdpc import Block

from world_interface.block_buffer import BlockBuffer


def fill_cuboid(
    buffer: BlockBuffer,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    block: Block,
) -> None:
    """
    Fill a solid rectangular volume with a block.

    Args:
        buffer:        BlockBuffer to write into.
        x1,y1,z1:     One corner of the volume.
        x2,y2,z2:     Opposite corner of the volume.
        block:         Block to fill with.
    """
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
                buffer.place(x, y, z, block)


def fill_cuboid_wireframe(
    buffer: BlockBuffer,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    block: Block,
) -> None:
    """
    Fill only the edges (wireframe) of a rectangular volume with a block.

    A position is on an edge when at least two of its three coordinates
    sit on a bounding face of the volume.

    Args:
        buffer:        BlockBuffer to write into.
        x1,y1,z1:     One corner of the volume.
        x2,y2,z2:     Opposite corner of the volume.
        block:         Block to place on edges.
    """
    xs = (min(x1, x2), max(x1, x2))
    ys = (min(y1, y2), max(y1, y2))
    zs = (min(z1, z2), max(z1, z2))
    for x in range(xs[0], xs[1] + 1):
        for y in range(ys[0], ys[1] + 1):
            for z in range(zs[0], zs[1] + 1):
                on_edge = (x in xs) + (y in ys) + (z in zs) >= 2
                if on_edge:
                    buffer.place(x, y, z, block)


def fill_line(
    buffer: BlockBuffer,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    block: Block,
) -> None:
    """
    Place blocks in a straight axis-aligned line between two points.

    Works for lines along X, Y, or Z. For diagonal lines use multiple
    calls or a dedicated Bresenham implementation.

    Args:
        buffer:        BlockBuffer to write into.
        x1,y1,z1:     Start point.
        x2,y2,z2:     End point.
        block:         Block to place.
    """
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
                buffer.place(x, y, z, block)