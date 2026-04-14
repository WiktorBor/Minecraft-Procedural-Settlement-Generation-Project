"""
structures/core/buffer_transform.py
-------------------------------------
Post-build coordinate and block-state rotation for BlockBuffers.

All structure grammars build axis-aligned (door on local-north face, etc.)
and return a plain BlockBuffer. When the plot requires a different facing,
the placement layer calls rotate_buffer() here once — after the grammar
has finished — to rotate the entire buffer around the footprint anchor.

This is the single location that knows about rotation. No other file in
structures/ needs to import or think about it.

Usage
-----
    buf = grammar.build(x, y, z, w, d)          # always axis-aligned

    rotation = facing_to_rotation(plot.facing)
    if rotation != 0:
        buf = rotate_buffer(buf, x, z, w, d, rotation)

    state.buildings.append(buf)                  # ready to flush
"""
from __future__ import annotations

from gdpc.transform import rotatedBoxTransform
from gdpc.vector_tools import Box

from world_interface.block_buffer import BlockBuffer


# ---------------------------------------------------------------------------
# Facing → rotation conversion
# ---------------------------------------------------------------------------

_FACING_TO_ROTATION: dict[str, int] = {
    "north":  0,
    "east":  90,
    "south": 180,
    "west":  270,
}


def facing_to_rotation(facing: str) -> int:
    """
    Convert a cardinal facing string to a clockwise rotation in degrees.

    Unknown values default to 0 (north).
    """
    return _FACING_TO_ROTATION.get((facing or "north").strip().lower(), 0)


# ---------------------------------------------------------------------------
# Buffer rotation
# ---------------------------------------------------------------------------

def rotate_buffer(
    buf: BlockBuffer,
    ox: int, oz: int,
    w: int, d: int,
    rotation: int,
) -> BlockBuffer:
    """
    Rotate all block positions and block states in buf by `rotation` degrees
    clockwise (0 / 90 / 180 / 270) around the footprint anchor (ox, oz).

    Uses GDPC's rotatedBoxTransform for coordinate rotation and
    Block.transformed() for block-state rotation — the same logic GDPC
    uses internally for pushTransform.

    Args:
        buf:      Source BlockBuffer (axis-aligned, built by a grammar).
        ox, oz:   World X/Z anchor — the top-left corner of the footprint
                  as passed to grammar.build().
        w, d:     Width and depth of the footprint as built (post-clamping).
        rotation: Clockwise degrees — 0, 90, 180, or 270.

    Returns:
        A new BlockBuffer with all positions and block states rotated.
        Returns buf unchanged when rotation == 0.
    """
    steps = (rotation // 90) % 4
    if steps == 0:
        return buf

    # Use a local-origin box so transform.apply() works in local space,
    # then translate back to world coordinates. Using Box(offset=(ox,0,oz))
    # causes the transform to treat the world offset as part of the rotation
    # math, producing positions hundreds of blocks from the intended location.
    box       = Box(offset=(0, 0, 0), size=(w, 1, d))
    transform = rotatedBoxTransform(box, steps)

    rotated = BlockBuffer()
    for (x, y, z), block in buf.items():
        local = transform.apply((x - ox, y, z - oz))
        rotated.place(
            int(local[0]) + ox, int(local[1]), int(local[2]) + oz,
            block.transformed(transform.rotation, transform.flip),
        )

    return rotated