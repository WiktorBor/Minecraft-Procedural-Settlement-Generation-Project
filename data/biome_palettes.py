from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class BiomePalette(TypedDict):
    """
    Block IDs for every material role used by the house grammar and builders.

    Required keys (all builders assume these exist):
        wall, roof, floor, foundation, path, accent,
        light, window, door, fence, slab, smoke

    The grammar never hardcodes a minecraft: string — it always reads from
    this palette so swapping biome changes the entire visual language of the
    settlement automatically.
    """
    wall:       str   # main wall block
    roof:       str   # stair block for roof slopes
    floor:      str   # interior floor block
    foundation: str   # stone base / foundation block
    path:       str   # road / path surface block
    accent:     str   # timber frame / decorative log
    light:      str   # lantern or torch
    window:     str   # glass pane or iron bars
    door:       str   # door block
    fence:      str   # fence post for porches / gardens
    slab:       str   # slab block matching foundation (for lintels / sills)
    smoke:      str   # block placed on chimney top (campfire / hay bale)
    prop:       str   # decorative prop beside door (barrel, pot, etc.)


BIOME_PALETTES: dict[str, BiomePalette] = {
    "plains": {
        "wall":       "minecraft:oak_planks",
        "roof":       "minecraft:dark_oak_stairs",
        "floor":      "minecraft:oak_planks",
        "foundation": "minecraft:cobblestone",
        "path":       "minecraft:dirt_path",
        "accent":     "minecraft:oak_log",
        "light":      "minecraft:torch",
        "window":     "minecraft:glass_pane",
        "door":       "minecraft:oak_door",
        "fence":      "minecraft:oak_fence",
        "slab":       "minecraft:cobblestone_slab",
        "smoke":      "minecraft:campfire",
        "prop":       "minecraft:barrel",
    },
    "desert": {
        "wall":       "minecraft:sandstone",
        "roof":       "minecraft:smooth_sandstone_stairs",
        "floor":      "minecraft:sandstone",
        "foundation": "minecraft:sandstone",
        "path":       "minecraft:sand",
        "accent":     "minecraft:cut_sandstone",
        "light":      "minecraft:torch",
        "window":     "minecraft:glass_pane",
        "door":       "minecraft:jungle_door",
        "fence":      "minecraft:jungle_fence",
        "slab":       "minecraft:sandstone_slab",
        "smoke":      "minecraft:hay_block",   # no fire in desert
        "prop":       "minecraft:flower_pot",
    },
    "taiga": {
        "wall":       "minecraft:spruce_planks",
        "roof":       "minecraft:spruce_stairs",
        "floor":      "minecraft:spruce_planks",
        "foundation": "minecraft:stone",
        "path":       "minecraft:gravel",
        "accent":     "minecraft:spruce_log",
        "light":      "minecraft:lantern",
        "window":     "minecraft:glass_pane",
        "door":       "minecraft:spruce_door",
        "fence":      "minecraft:spruce_fence",
        "slab":       "minecraft:stone_slab",
        "smoke":      "minecraft:campfire",
        "prop":       "minecraft:barrel",
    },
    "mountain": {
        "wall":       "minecraft:stone_bricks",
        "roof":       "minecraft:stone_brick_stairs",
        "floor":      "minecraft:stone_bricks",
        "foundation": "minecraft:cobblestone",
        "path":       "minecraft:cobblestone",
        "accent":     "minecraft:stone",
        "light":      "minecraft:lantern",
        "window":     "minecraft:iron_bars",
        "door":       "minecraft:spruce_door",
        "fence":      "minecraft:spruce_fence",
        "slab":       "minecraft:cobblestone_slab",
        "smoke":      "minecraft:campfire",
        "prop":       "minecraft:barrel",
    },
    "medieval": {
        "wall":       "minecraft:stone_bricks",
        "roof":       "minecraft:spruce_stairs",
        "floor":      "minecraft:spruce_planks",
        "foundation": "minecraft:cobblestone",
        "path":       "minecraft:cobblestone",
        "accent":     "minecraft:dark_oak_log",
        "light":      "minecraft:lantern",
        "window":     "minecraft:iron_bars",
        "door":       "minecraft:dark_oak_door",
        "fence":      "minecraft:dark_oak_fence",
        "slab":       "minecraft:cobblestone_slab",
        "smoke":      "minecraft:campfire",
        "prop":       "minecraft:barrel",
    },
}

_FALLBACK_BIOME = "plains"


def get_biome_palette(biome_type: str = _FALLBACK_BIOME) -> BiomePalette:
    """
    Return a copy of the block palette for the given biome type.

    Falls back to 'plains' with a warning if the biome is not recognised.
    """
    if biome_type not in BIOME_PALETTES:
        logger.warning(
            "Unknown biome type %r — falling back to %r.",
            biome_type, _FALLBACK_BIOME,
        )
        biome_type = _FALLBACK_BIOME
    return dict(BIOME_PALETTES[biome_type])  # type: ignore[return-value]


def palette_get(palette: BiomePalette, key: str, default: str = "minecraft:stone") -> str:
    """Safely get an optional palette key, returning `default` if absent."""
    return palette.get(key, default)  # type: ignore[return-value]