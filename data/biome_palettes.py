from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class BiomePalette(TypedDict, total=False):
    """
    Block IDs for each material role in a biome.

    Required keys: wall, roof, floor, foundation, path, accent.
    Optional keys: wall_secondary, light, window, door, fence,
                   roof_slab, smoke, moss, ceiling_slab, accent_beam,
                   interior_light.
    """
    # Core roles (always present)
    wall:        str
    roof:        str
    floor:       str
    foundation:  str
    path:        str
    accent:      str

    # Optional roles (accessed via palette_get with a default)
    wall_secondary: str
    light:          str
    window:         str
    door:           str
    fence:          str
    roof_slab:      str
    smoke:          str
    moss:           str
    ceiling_slab:   str
    accent_beam:    str
    interior_light: str


# ---------------------------------------------------------------------------
# Palette definitions — treated as constants, never mutate directly
# ---------------------------------------------------------------------------

BIOME_PALETTES: dict[str, BiomePalette] = {
    "plains": {
        "wall":           "minecraft:oak_planks",
        "wall_secondary": "minecraft:cobblestone",
        "roof":           "minecraft:dark_oak_stairs",
        "roof_slab":      "minecraft:dark_oak_slab",
        "floor":          "minecraft:oak_planks",
        "foundation":     "minecraft:cobblestone",
        "path":           "minecraft:dirt_path",
        "accent":         "minecraft:oak_log",
        "accent_beam":    "minecraft:stripped_oak_log",
        "light":          "minecraft:lantern",
        "window":         "minecraft:glass_pane",
        "door":           "minecraft:oak_door",
        "fence":          "minecraft:oak_fence",
        "smoke":          "minecraft:campfire",
        "moss":           "minecraft:moss_carpet",
        "ceiling_slab":   "minecraft:oak_slab",
        "interior_light": "minecraft:pearlescent_froglight",
    },
    "desert": {
        "wall":           "minecraft:sandstone",
        "wall_secondary": "minecraft:smooth_sandstone",
        "roof":           "minecraft:smooth_sandstone_stairs",
        "roof_slab":      "minecraft:smooth_sandstone_slab",
        "floor":          "minecraft:sandstone",
        "foundation":     "minecraft:sandstone",
        "path":           "minecraft:sand",
        "accent":         "minecraft:cut_sandstone",
        "accent_beam":    "minecraft:stripped_oak_log",
        "light":          "minecraft:lantern",
        "window":         "minecraft:glass_pane",
        "door":           "minecraft:oak_door",
        "fence":          "minecraft:oak_fence",
        "smoke":          "minecraft:campfire",
        "moss":           "minecraft:moss_carpet",
        "ceiling_slab":   "minecraft:sandstone_slab",
        "interior_light": "minecraft:pearlescent_froglight",
    },
    "taiga": {
        "wall":           "minecraft:spruce_planks",
        "wall_secondary": "minecraft:stone",
        "roof":           "minecraft:spruce_stairs",
        "roof_slab":      "minecraft:spruce_slab",
        "floor":          "minecraft:spruce_planks",
        "foundation":     "minecraft:stone",
        "path":           "minecraft:gravel",
        "accent":         "minecraft:spruce_log",
        "accent_beam":    "minecraft:stripped_spruce_log",
        "light":          "minecraft:lantern",
        "window":         "minecraft:glass_pane",
        "door":           "minecraft:spruce_door",
        "fence":          "minecraft:spruce_fence",
        "smoke":          "minecraft:campfire",
        "moss":           "minecraft:moss_carpet",
        "ceiling_slab":   "minecraft:spruce_slab",
        "interior_light": "minecraft:pearlescent_froglight",
    },
    "mountain": {
        "wall":           "minecraft:stone_bricks",
        "wall_secondary": "minecraft:cobblestone",
        "roof":           "minecraft:stone_brick_stairs",
        "roof_slab":      "minecraft:stone_brick_slab",
        "floor":          "minecraft:stone_bricks",
        "foundation":     "minecraft:cobblestone",
        "path":           "minecraft:cobblestone",
        "accent":         "minecraft:stone",
        "accent_beam":    "minecraft:stripped_spruce_log",
        "light":          "minecraft:lantern",
        "window":         "minecraft:iron_bars",
        "door":           "minecraft:spruce_door",
        "fence":          "minecraft:spruce_fence",
        "smoke":          "minecraft:campfire",
        "moss":           "minecraft:moss_carpet",
        "ceiling_slab":   "minecraft:stone_brick_slab",
        "interior_light": "minecraft:pearlescent_froglight",
    },
    "medieval": {
        "wall":           "minecraft:stone_bricks",
        "wall_secondary": "minecraft:cobblestone",
        "roof":           "minecraft:spruce_stairs",
        "roof_slab":      "minecraft:spruce_slab",
        "floor":          "minecraft:spruce_planks",
        "foundation":     "minecraft:cobblestone",
        "path":           "minecraft:cobblestone",
        "accent":         "minecraft:stripped_dark_oak_log",
        "accent_beam":    "minecraft:stripped_spruce_log",
        "light":          "minecraft:lantern",
        "window":         "minecraft:brown_stained_glass",
        "door":           "minecraft:oak_door",
        "fence":          "minecraft:spruce_fence",
        "smoke":          "minecraft:campfire",
        "moss":           "minecraft:moss_carpet",
        "ceiling_slab":   "minecraft:oak_slab",
        "interior_light": "minecraft:pearlescent_froglight",
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
    """Safely retrieve an optional palette key, returning `default` if absent."""
    return palette.get(key, default)  # type: ignore[return-value]