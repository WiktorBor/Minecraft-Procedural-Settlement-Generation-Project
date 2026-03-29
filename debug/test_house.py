"""
test_house.py
-------------
Standalone house placement tester.

Run this from the project root while your Minecraft server is running:

    python test_house.py

It connects to the server, finds your player position, and places a single
house just in front of you. Tweak the TWEAK ZONE below and re-run to see
changes immediately in-game.

Controls
--------
- Change HOUSE_PARAMS to force specific grammar parameters (bypasses the scorer).
- Set HOUSE_PARAMS = None to let the grammar sample + score freely.
- Change PALETTE_NAME to try different biome materials.
- Change OFFSET to move where the house is placed relative to you.
- Set CLEAR_FIRST = True to remove the previous house before placing a new one.
- Set SEED to a fixed int for reproducible results, or None for random.
"""
from __future__ import annotations

import logging
import sys
import random
from pathlib import Path

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from gdpc import Editor, Block
from gdpc.vector_tools import ivec3

from data.biome_palettes import get_biome_palette
from data.settlement_entities import Plot
from structures.house.house_grammar import HouseGrammar
from structures.house.house_scorer import HouseParams

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_house")


# =============================================================================
# ✏️  TWEAK ZONE — edit these to change what gets built
# =============================================================================

# Seed — set to an int for reproducible results, None for random each run
SEED: int | None = 42

# How far in front of you the house origin is placed (x, y_offset, z)
# y_offset=0 means same Y as your feet — raise if house appears underground
OFFSET: tuple[int, int, int] = (5, 0, 5)

# Plot size — change these to test different house footprints
PLOT_WIDTH: int = 10
PLOT_DEPTH: int = 10

# Palette — try "medieval", "desert", "snowy", "savanna"
PALETTE_NAME: str = "medieval"

# Clear a box around the plot before building (useful for re-testing)
CLEAR_FIRST: bool = True

# Force specific grammar parameters — set to None to let grammar decide freely.
# Only the fields you set here are overridden; the grammar fills the rest.
#
# To force a two-storey house with a steep roof:
#   FORCE_PARAMS = {"has_upper": True, "roof_type": "steep", "wall_h": 4}
#
# To force a small single-storey cottage:
#   FORCE_PARAMS = {"has_upper": False, "roof_type": "gabled", "wall_h": 3}
#
# Set to None to let the scorer decide:
#   FORCE_PARAMS = None
FORCE_PARAMS: dict | None = {
    # Uncomment and edit any of these:
    "has_upper":     True,
    "upper_h":       3,
    "roof_type":     "cross",    # "gabled" | "steep" | "cross"
    "wall_h":        5,
    "has_chimney":   True,
    "has_porch":     True,
    "has_extension": False,
    "foundation_h":  1,
}

# Rotation — 0, 90, 180, or 270
ROTATION: int = 0

# Random offset — if True, places the house at a random position each run
# within RANDOM_OFFSET_RANGE blocks of your position (ignores OFFSET).
# Useful for comparing multiple houses side by side without moving.
# If False, always uses the fixed OFFSET above.
RANDOM_OFFSET: bool = False
RANDOM_OFFSET_RANGE: tuple[int, int] = (5, 40)   # min and max blocks from player

# =============================================================================
# End of tweak zone
# =============================================================================


def _get_player_pos(editor: Editor) -> tuple[int, int, int]:
    """
    Return the first online player position as (x, y, z).

    Tries multiple GDPC API patterns across versions:
      1. editor.getPlayerPos()          — older GDPC
      2. editor.getPlayers()[0].pos     — newer GDPC
      3. Direct HTTP GET /players       — fallback, works on all versions

    Falls back to build area centre if no player is found.
    """
    import requests

    # Try 1: direct HTTP /players with includeData=true
    # Position is inside the NBT data string: Pos:[-3.48d,-58.74d,-16.57d]
    try:
        import re
        resp = requests.get("http://localhost:9000/players?includeData=true", timeout=3)
        if resp.ok:
            players = resp.json()
            if players:
                p = players[0]
                data_str = p.get("data", "")
                # Parse Pos:[xd,yd,zd] from NBT string
                match = re.search(r"Pos:\[([\-0-9.]+)d,([\-0-9.]+)d,([\-0-9.]+)d\]", data_str)
                if match:
                    px = int(float(match.group(1)))
                    py = int(float(match.group(2)))
                    pz = int(float(match.group(3)))
                    logger.info("Player position from /players: (%d, %d, %d)", px, py, pz)
                    return px, py, pz
    except Exception as e:
        logger.debug("HTTP /players failed: %s", e)

    # Try 2: editor.getPlayerPos() — older GDPC versions
    try:
        pos = editor.getPlayerPos()
        return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayerPos() failed: %s", e)

    # Try 3: editor.getPlayers() — newer GDPC versions
    try:
        players = editor.getPlayers()
        if players:
            pos = players[0].pos
            return int(pos.x), int(pos.y), int(pos.z)
    except Exception as e:
        logger.debug("editor.getPlayers() failed: %s", e)

    # Fallback: build area centre
    logger.warning(
        "Could not get player position — falling back to build area centre. "
        "Make sure you are online in the world."
    )
    build_area = editor.getBuildArea()
    cx = build_area.offset.x + build_area.size.x // 2
    cz = build_area.offset.z + build_area.size.z // 2
    return cx, 64, cz


def clear_box(editor: Editor, x: int, y: int, z: int, w: int, d: int, h: int = 20) -> None:
    """Clear a box of air above the plot so old houses don't bleed through."""
    positions = [
        (x + dx, y + dy, z + dz)
        for dx in range(w + 4)
        for dz in range(d + 4)
        for dy in range(-2, h)
    ]
    logger.info("Clearing %d blocks...", len(positions))
    editor.placeBlock(positions, Block("minecraft:air"))


def get_ground_y(editor: Editor, x: int, z: int, start_y: int) -> int:
    """
    Walk downward from start_y until we find a non-air block.
    Returns the Y of the top solid block (the surface).
    """
    for y in range(start_y, start_y - 30, -1):
        block = editor.getBlock((x, y, z))
        if block.id not in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air"):
            return y
    return start_y  # fallback


def apply_force_params(grammar: HouseGrammar, plot: Plot, force: dict) -> None:
    """
    Monkey-patch _make_context to inject forced parameters.
    Only the keys present in `force` are overridden.
    """
    original_make_context = grammar._make_context

    def patched_make_context(p: Plot, rotation: int):
        ctx = original_make_context(p, rotation)
        for key, val in force.items():
            if hasattr(ctx, key):
                object.__setattr__(ctx, key, val)
            else:
                logger.warning("FORCE_PARAMS key '%s' not found on _Ctx — ignored.", key)
        return ctx

    grammar._make_context = patched_make_context


def main() -> None:
    if SEED is not None:
        random.seed(SEED)

    logger.info("Connecting to Minecraft server...")
    editor = Editor(buffering=True)

    try:
        editor.checkConnection()
    except Exception as e:
        logger.error("Could not connect: %s", e)
        logger.error("Make sure your Minecraft server is running with GDPC HTTP interface.")
        sys.exit(1)

    logger.info("Connected.")

    # --- find player position ---
    # Query the GDPC /players endpoint directly — more reliable than
    # editor.getPlayerPos() which varies across GDPC versions.
    px, py, pz = _get_player_pos(editor)
    logger.info("Player position: (%d, %d, %d)", px, py, pz)

    # --- compute house origin ---
    if RANDOM_OFFSET:
        lo, hi = RANDOM_OFFSET_RANGE
        ox = random.randint(lo, hi) * random.choice([-1, 1])
        oz = random.randint(lo, hi) * random.choice([-1, 1])
        oy_offset = 0
        logger.info("Random offset: (%d, %d)", ox, oz)
    else:
        ox, oy_offset, oz = OFFSET
    hx = px + ox
    hz = pz + oz

    # Walk down to find actual ground level at house origin
    hy = get_ground_y(editor, hx, hz, py + oy_offset)
    logger.info("House origin: (%d, %d, %d)", hx, hy, hz)

    # --- build the plot ---
    plot = Plot(
        x=hx,
        y=hy,
        z=hz,
        width=PLOT_WIDTH,
        depth=PLOT_DEPTH,
        type="residential",
    )

    palette = get_biome_palette(PALETTE_NAME)

    # --- optionally clear the area first ---
    if CLEAR_FIRST:
        clear_box(editor, hx - 2, hy, hz - 2, PLOT_WIDTH, PLOT_DEPTH)
        editor.flushBuffer()
        logger.info("Area cleared.")

    # --- build the house ---
    grammar = HouseGrammar(editor=editor, palette=palette)

    if FORCE_PARAMS:
        logger.info("Applying forced parameters: %s", FORCE_PARAMS)
        apply_force_params(grammar, plot, FORCE_PARAMS)

    logger.info(
        "Building %dx%d house at (%d,%d,%d) rotation=%d palette=%s ...",
        PLOT_WIDTH, PLOT_DEPTH, hx, hy, hz, ROTATION, PALETTE_NAME,
    )

    grammar.build(plot, rotation=ROTATION)
    # grammar.build_test(plot, roof_type="cross", w=7, d=7)
    # grammar.build_test(plot, roof_type="cross", w=5, d=9)
    # grammar.build_test(plot, roof_type="gabled", w=6, d=8)
    editor.flushBuffer()
    logger.info("Done — teleport to the house with: /tp %d %d %d", hx, hy + 5, hz - 5)


if __name__ == "__main__":
    main()