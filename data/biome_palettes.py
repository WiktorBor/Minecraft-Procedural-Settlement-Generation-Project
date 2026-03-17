from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class BiomePalette(TypedDict):
    """Block IDs for each material role in a biome."""
    wall:       str
    roof:       str
    floor:      str
    foundation: str
    path:       str
    accent:     str


# Biome material palettes — treated as constants; never mutate directly.
BIOME_PALETTES: dict[str, BiomePalette] = {
    "plains": {
        "wall":       "minecraft:oak_planks",
        "roof":       "minecraft:dark_oak_stairs",
        "floor":      "minecraft:oak_planks",
        "foundation": "minecraft:cobblestone",
        "path":       "minecraft:dirt_path",
        "accent":     "minecraft:oak_log",
    },
    "desert": {
        "wall":       "minecraft:sandstone",
        "roof":       "minecraft:smooth_sandstone_stairs",
        "floor":      "minecraft:sandstone",
        "foundation": "minecraft:sandstone",
        "path":       "minecraft:sand",
        "accent":     "minecraft:cut_sandstone",
    },
    "taiga": {
        "wall":       "minecraft:spruce_planks",
        "roof":       "minecraft:spruce_stairs",
        "floor":      "minecraft:spruce_planks",
        "foundation": "minecraft:stone",
        "path":       "minecraft:gravel",
        "accent":     "minecraft:spruce_log",
    },
    "mountain": {
        "wall":       "minecraft:stone_bricks",
        "roof":       "minecraft:stone_brick_stairs",
        "floor":      "minecraft:stone_bricks",
        "foundation": "minecraft:cobblestone",
        "path":       "minecraft:cobblestone",
        "accent":     "minecraft:stone",
    },
}

_FALLBACK_BIOME = "plains"


def get_biome_palette(biome_type: str = _FALLBACK_BIOME) -> BiomePalette:
    """
    Return a copy of the block palette for the given biome type.

    Falls back to 'plains' with a warning if the biome is not recognised.

    Parameters
    ----------
    biome_type : str
        One of the keys in BIOME_PALETTES ('plains', 'desert', 'taiga', 'mountain').

    Returns
    -------
    BiomePalette
        Mapping of material roles to Minecraft block IDs.
        Keys: 'wall', 'roof', 'floor', 'foundation', 'path', 'accent'.
    """
    if biome_type not in BIOME_PALETTES:
        logger.warning(
            "Unknown biome type %r — falling back to %r.",
            biome_type, _FALLBACK_BIOME,
        )
        biome_type = _FALLBACK_BIOME

    # Return a copy to prevent accidental mutation of the global constant
    return dict(BIOME_PALETTES[biome_type])  # type: ignore[return-value]