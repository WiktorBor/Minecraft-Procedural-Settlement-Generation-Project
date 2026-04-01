"""
test_templates.py
-----------------
Test script for structure templates.

Connects to Minecraft, finds your player position, and places each template
in a row in front of you.  After each build prints a per-layer coordinate
report so you can verify wall/roof positions.

Usage
-----
    python3 debug/test_templates.py

Controls
--------
    TEMPLATES_TO_BUILD   — which templates to place
    TEMPLATE_SIZES       — (width, depth) per template
    PALETTE_NAME         — biome palette ("plains", "medieval", "desert", ...)
    STARTING_OFFSET      — (x, y_offset, z) relative to player
    SPACING              — gap in Z between structures
    CLEAR_FIRST          — wipe the area before each build
    SEED                 — int for reproducible results, None for random
"""
from __future__ import annotations

import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # project root

from gdpc import Editor, Block

from data.biome_palettes import get_biome_palette
from data.settlement_entities import Plot
from structures.house.house_grammar import HouseGrammar
from structures.misc.blacksmith import Blacksmith
from structures.misc.clock_tower import ClockTower
from structures.misc.market_stall import MarketStall
from structures.misc.tavern import Tavern
from structures.misc.square_centre import SquareCentre
from structures.tower.tower import Tower
from structures.misc.fortification import Fortification
from structures.misc.spire_tower import SpireTower

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_templates")


# =============================================================================
# TWEAK ZONE
# =============================================================================

TEMPLATES_TO_BUILD = [
    "tower",
    "spire_tower",
    "fortification",
]

TEMPLATE_SIZES = {
    "house":          (9, 9),
    "blacksmith":     (8, 10),
    "market_stall":   (6, 6),
    "plaza_small":    (12, 12),   # radius=6  → small_fountain style
    "plaza_large":    (20, 20),   # radius=10 → grand_spire style
    "clock_tower":    (10, 10),
    "tavern":         (22, 14),
    "tower":          (7, 7),
    "spire_tower":    (13, 8),
    "fortification":  (17, 7),    # fits 4 arches
}

PALETTE_NAME:    str                  = "plains"
STARTING_OFFSET: tuple[int, int, int] = (5, 0, 5)
SPACING:         int                  = 18
CLEAR_FIRST:     bool                 = True
SEED:            int | None           = 42

# =============================================================================


# ---------------------------------------------------------------------------
# Coordinate logger
# ---------------------------------------------------------------------------

class _CoordinateLogger:
    """
    Wraps a GDPC Editor, intercepts every placeBlock call, and records
    positions grouped by Y level.  Call .report() after a build.
    """

    def __init__(self, real_editor) -> None:
        self._editor = real_editor
        self._by_y: dict[int, dict] = {}

    def placeBlock(self, position, block) -> None:
        positions = position if isinstance(position, list) else [position]
        for pos in positions:
            self._record(int(pos[0]), int(pos[1]), int(pos[2]), block)
        self._editor.placeBlock(position, block)

    def _record(self, x: int, y: int, z: int, block) -> None:
        if y not in self._by_y:
            self._by_y[y] = {"xs": [], "zs": [], "blocks": set()}
        self._by_y[y]["xs"].append(x)
        self._by_y[y]["zs"].append(z)
        self._by_y[y]["blocks"].add(getattr(block, "id", str(block)))

    def report(self, base_x: int, base_y: int, base_z: int, w: int, d: int) -> None:
        if not self._by_y:
            logger.info("  [coords] No blocks recorded.")
            return

        ys = sorted(self._by_y.keys())

        logger.info("")
        logger.info("  ┌─ COORDINATE REPORT ─────────────────────────────────────────────")
        logger.info("  │  Plot  x=%d  y=%d  z=%d  w=%d  d=%d", base_x, base_y, base_z, w, d)
        logger.info("  │  Y     %d → %d  (%d layers)", ys[0], ys[-1], len(ys))
        logger.info("  │")
        logger.info(
            "  │  %-5s  %-22s  %-16s  %-16s  %s",
            "y", "module", "x range", "z range", "blocks",
        )
        logger.info("  │  " + "─" * 85)

        for abs_y in ys:
            info           = self._by_y[abs_y]
            rel            = abs_y - base_y
            x_lo, x_hi    = min(info["xs"]), max(info["xs"])
            z_lo, z_hi    = min(info["zs"]), max(info["zs"])
            n              = len(info["xs"])
            blist          = sorted(info["blocks"])
            bstr           = blist[0].replace("minecraft:", "") if blist else "?"
            if len(blist) > 1:
                bstr += f" +{len(blist) - 1}"

            if rel < 0:
                module = f"foundation  (rel {rel})"
            elif rel == 0:
                module = "floor       (rel  0)"
            elif rel <= 4:
                module = f"walls       (rel +{rel})"
            elif rel == 5:
                module = f"ceiling     (rel +{rel})"
            elif rel <= 8:
                module = f"upper walls (rel +{rel})"
            else:
                module = f"roof        (rel +{rel})"

            logger.info(
                "  │  %-5d  %-22s  x=[%d,%d]  z=[%d,%d]  n=%-4d  %s",
                abs_y, module, x_lo, x_hi, z_lo, z_hi, n, bstr,
            )

        logger.info("  └─────────────────────────────────────────────────────────────────")
        logger.info("")
        self._by_y.clear()

    def getBlock(self, pos):
        return self._editor.getBlock(pos)

    def flushBuffer(self) -> None:
        self._editor.flushBuffer()

    def __getattr__(self, name):
        return getattr(self._editor, name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    import re
    import requests

    try:
        resp = requests.get("http://localhost:9000/players?includeData=true", timeout=3)
        if resp.ok:
            players = resp.json()
            if players:
                m = re.search(
                    r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]",
                    players[0].get("data", ""),
                )
                if m:
                    return int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3)))
    except Exception:
        pass

    try:
        pos = editor.getPlayerPos()
        return int(pos.x), int(pos.y), int(pos.z)
    except Exception:
        pass

    try:
        players = editor.getPlayers()
        if players:
            pos = players[0].pos
            return int(pos.x), int(pos.y), int(pos.z)
    except Exception:
        pass

    ba = editor.getBuildArea()
    return ba.offset.x + ba.size.x // 2, 64, ba.offset.z + ba.size.z // 2


def _ground_y(editor: Editor, x: int, z: int, start_y: int) -> int:
    for y in range(start_y, start_y - 30, -1):
        bid = editor.getBlock((x, y, z)).id
        if bid not in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air"):
            return y
    return start_y


def _clear(editor: Editor, x: int, y: int, z: int, w: int, d: int) -> None:
    positions = [
        (x + dx, y + dy, z + dz)
        for dx in range(w + 4)
        for dz in range(d + 4)
        for dy in range(-2, 20)
    ]
    editor.placeBlock(positions, Block("minecraft:air"))
    editor.flushBuffer()


def _build(name: str, coord_log: _CoordinateLogger, plot: Plot, palette, editor) -> None:
    """Dispatch to the correct class based on template name."""
    rotation = random.choice([0, 90, 180, 270])
    if name == "house":
        grammar = HouseGrammar(coord_log, palette)
        grammar.build(plot, rotation=rotation)
    elif name == "blacksmith":
        Blacksmith().build(coord_log, plot, palette, rotation=rotation)
    elif name == "market_stall":
        MarketStall().build(coord_log, plot, palette)
    elif name in ("plaza", "plaza_small", "plaza_large"):
        SquareCentre().build(coord_log, plot, palette)
    elif name == "clock_tower":
        ClockTower().build(coord_log, plot, palette)
    elif name == "tavern":
        Tavern().build(coord_log, plot, palette)
    elif name == "tower":
        Tower().build(coord_log, plot, palette, rotation=rotation)
    elif name == "spire_tower":
        SpireTower().build(coord_log, plot, palette, rotation=rotation)
    elif name == "fortification":
        Fortification().build(coord_log, plot, palette, rotation=rotation)
    else:
        raise ValueError(f"Unknown template name: '{name}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if SEED is not None:
        random.seed(SEED)

    logger.info("Connecting to Minecraft...")
    editor = Editor(buffering=True)
    try:
        editor.checkConnection()
    except Exception as e:
        logger.error("Could not connect: %s", e)
        sys.exit(1)
    logger.info("Connected.")

    px, py, pz = _get_player_pos(editor)
    logger.info("Player: (%d, %d, %d)", px, py, pz)

    ox, oy, oz = STARTING_OFFSET
    start_x    = px + ox
    start_z    = pz + oz
    base_y     = _ground_y(editor, start_x, start_z, py + oy)
    logger.info("Build start: (%d, %d, %d)", start_x, base_y, start_z)

    palette   = get_biome_palette(PALETTE_NAME)
    coord_log = _CoordinateLogger(editor)
    current_z = start_z

    for name in TEMPLATES_TO_BUILD:
        if name not in TEMPLATE_SIZES:
            logger.warning("Unknown template '%s' — skipping.", name)
            continue

        w, d = TEMPLATE_SIZES[name]
        x, z = start_x, current_z
        plot = Plot(x=x, z=z, y=base_y, width=w, depth=d)

        logger.info("── %s  (%dx%d)  at (%d, %d, %d) ──", name, w, d, x, base_y, z)

        if CLEAR_FIRST:
            _clear(editor, x, base_y, z, w, d)

        try:
            _build(name, coord_log, plot, palette, editor)
            editor.flushBuffer()
            logger.info("  ✓ built")
            coord_log.report(x, base_y, z, w, d)
        except Exception as e:
            logger.error("  ✗ FAILED: %s", e, exc_info=True)

        current_z += d + SPACING

    logger.info("Done. Teleport commands:")
    current_z = start_z
    for name in TEMPLATES_TO_BUILD:
        if name not in TEMPLATE_SIZES:
            continue
        w, d = TEMPLATE_SIZES[name]
        logger.info("  %-15s  /tp %d %d %d", name, start_x, base_y + 5, current_z + d // 2)
        current_z += d + SPACING


if __name__ == "__main__":
    main()