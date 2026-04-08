"""
test_tavern.py
--------------
Standalone tavern placement tester.

Run from the project root while your Minecraft server is running:

    python debug/test_tavern.py

Places a single tavern just in front of your player position.

Controls
--------
- PALETTE_NAME  — biome material set ("medieval", "desert", "snowy", "savanna")
- OFFSET        — (x, y_offset, z) relative to player position
- PLOT_WIDTH    — plot width (min 20 for a full three-part tavern)
- PLOT_DEPTH    — plot depth (min 12)
- ROTATION      — 0 / 90 / 180 / 270
- CLEAR_FIRST   — wipe the area before building
- SEED          — fixed int for reproducible results, None for random
"""
from __future__ import annotations

import logging
import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gdpc import Editor, Block

from data.biome_palettes import get_biome_palette
from data.settlement_entities import Plot
from structures.misc.tavern import Tavern
from world_interface.structure_placer import StructurePlacer

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_tavern")

# =============================================================================
# TWEAK ZONE
# =============================================================================

SEED: int | None = 42

OFFSET: tuple[int, int, int] = (5, 0, 5)

PLOT_WIDTH: int = 24   # min 19 (tower>=5 + bridge>=7 + cottage>=7)
PLOT_DEPTH: int = 12   # min 8

PALETTE_NAME: str = "medieval"

CLEAR_FIRST: bool = True

ROTATION: int = 0   # 0 / 90 / 180 / 270

WITH_TOWER:  bool = True   # set False to skip the stone tower
WITH_BRIDGE: bool = True   # set False to skip the arched bridge

# =============================================================================


def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    import requests, re
    try:
        resp = requests.get("http://localhost:9000/players?includeData=true", timeout=3)
        if resp.ok:
            players = resp.json()
            if players:
                match = re.search(
                    r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]",
                    players[0].get("data", ""),
                )
                if match:
                    return (int(float(match.group(1))),
                            int(float(match.group(2))),
                            int(float(match.group(3))))
    except Exception as e:
        logger.debug("HTTP /players failed: %s", e)

    try:
        pos = editor.getPlayerPos()
        return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayerPos() failed: %s", e)

    try:
        players = editor.getPlayers()
        if players:
            pos = players[0].pos
            return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayers() failed: %s", e)

    build_area = editor.getBuildArea()
    cx = build_area.offset.x + build_area.size.x // 2
    cz = build_area.offset.z + build_area.size.z // 2
    logger.warning("Falling back to build area centre.")
    return cx, 64, cz


def clear_box(editor: Editor, x: int, y: int, z: int, w: int, d: int, h: int = 25) -> None:
    positions = [
        (x + dx, y + dy, z + dz)
        for dx in range(w + 4)
        for dz in range(d + 4)
        for dy in range(-2, h)
    ]
    logger.info("Clearing %d blocks...", len(positions))
    editor.placeBlock(positions, Block("minecraft:air"))


def get_ground_y(editor: Editor, x: int, z: int, start_y: int) -> int:
    for y in range(start_y, start_y - 30, -1):
        block = editor.getBlock((x, y, z))
        if block.id not in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air"):
            return y
    return start_y


def main() -> None:
    if SEED is not None:
        random.seed(SEED)

    logger.info("Connecting to Minecraft server...")
    editor = Editor(buffering=True)

    try:
        editor.checkConnection()
    except Exception as e:
        logger.error("Could not connect: %s", e)
        sys.exit(1)

    logger.info("Connected.")
    px, py, pz = _get_player_pos(editor)
    logger.info("Player position: (%d, %d, %d)", px, py, pz)

    ox, oy_offset, oz = OFFSET
    hx = px + ox
    hz = pz + oz
    hy = get_ground_y(editor, hx, hz, py + oy_offset)
    logger.info("Plot origin: (%d, %d, %d)", hx, hy, hz)

    plot = Plot(x=hx, y=hy, z=hz, width=PLOT_WIDTH, depth=PLOT_DEPTH, type="residential")
    palette = get_biome_palette(PALETTE_NAME)

    if CLEAR_FIRST:
        clear_box(editor, hx - 2, hy, hz - 2, PLOT_WIDTH, PLOT_DEPTH)
        editor.flushBuffer()
        logger.info("Area cleared.")

    logger.info(
        "Building tavern %dx%d at (%d,%d,%d) rotation=%d palette=%s ...",
        PLOT_WIDTH, PLOT_DEPTH, hx, hy, hz, ROTATION, PALETTE_NAME,
    )

    buf = Tavern().build(plot, palette, rotation=ROTATION,
                         with_tower=WITH_TOWER, with_bridge=WITH_BRIDGE)
    if not buf:
        logger.error("Tavern returned an empty buffer — check PLOT_WIDTH >= 19 and PLOT_DEPTH >= 8.")
        sys.exit(1)

    logger.info("Buffer contains %d blocks.", len(buf))
    StructurePlacer(editor).place(buf)
    logger.info("Done — /tp %d %d %d", hx, hy + 5, hz - 5)


if __name__ == "__main__":
    main()
