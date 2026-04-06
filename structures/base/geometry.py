"""Geometry helpers that write to a BlockBuffer instead of an Editor."""
from __future__ import annotations

from gdpc import Block

from world_interface.block_buffer import BlockBuffer


def fill_cuboid(
    buffer: BlockBuffer,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    block: Block,
) -> None:
    """Fill a solid rectangular volume with a block."""
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
    """Fill only the edges (wireframe) of a rectangular volume."""
    xs = (min(x1, x2), max(x1, x2))
    ys = (min(y1, y2), max(y1, y2))
    zs = (min(z1, z2), max(z1, z2))
    for x in range(xs[0], xs[1] + 1):
        for y in range(ys[0], ys[1] + 1):
            for z in range(zs[0], zs[1] + 1):
                on_edge = (
                    (x in xs) + (y in ys) + (z in zs) >= 2
                )
                if on_edge:
                    buffer.place(x, y, z, block)


def fill_line(
    buffer: BlockBuffer,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    block: Block,
) -> None:
    """Place blocks in a straight line between two points (axis-aligned only)."""
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
                buffer.place(x, y, z, block)
