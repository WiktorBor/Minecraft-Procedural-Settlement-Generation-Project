"""
palette/material_library.py
----------------------------
Archetype-keyed material library for the PaletteSystem.

Each entry defines structure materials, road materials, and per-district
overrides.  All block IDs are WITHOUT the "minecraft:" prefix — the
PaletteSystem adds it.

Weighted variants format:
    {"variants": ["block_a", "block_b"], "weights": [0.7, 0.3]}
"""
from __future__ import annotations

MATERIAL_LIBRARY: dict = {

    # -----------------------------------------------------------------------
    # TEMPERATE — plains, forest, meadow, birch forest
    # -----------------------------------------------------------------------
    "TEMPERATE": {
        "structure": {
            "primary_wall":   {"variants": ["stone_bricks", "cobblestone", "mossy_cobblestone"],
                               "weights":  [0.50, 0.30, 0.20]},
            "foundation":     "cobblestone",
            "frame":          "oak_log",
            "roof":           {"block": "oak_planks", "stairs": "oak_stairs", "slab": "oak_slab"},
            "decor": {
                "door":    "oak_door",
                "window":  "glass_pane",
                "fence":   "oak_fence",
                "light":   ["lantern", "torch"],
                "plaster": "calcite",
            },
        },
        "districts": {
            "centre":      {"wall": "stone_bricks", "foundation": "stone_bricks"},
            "residential": {},
            "farming":     {"wall": "cobblestone", "floor": "dirt"},
            "fishing":     {"wall": "oak_planks",  "foundation": "cobblestone"},
            "forest":      {"wall": "mossy_cobblestone"},
        },
        "roads": {
            "main": {"variants": ["stone_bricks", "cobblestone"], "weights": [0.60, 0.40]},
            "path": {"variants": ["dirt_path", "coarse_dirt"],    "weights": [0.70, 0.30]},
            "edge": "cobblestone_slab",
        },
    },

    # -----------------------------------------------------------------------
    # FROZEN — taiga, snowy tundra, ice spikes, frozen peaks
    # -----------------------------------------------------------------------
    "FROZEN": {
        "structure": {
            "primary_wall":   {"variants": ["stone_bricks", "packed_ice", "cobblestone"],
                               "weights":  [0.55, 0.25, 0.20]},
            "foundation":     "stone_bricks",
            "frame":          "spruce_log",
            "roof":           {"block": "spruce_planks", "stairs": "spruce_stairs", "slab": "spruce_slab"},
            "decor": {
                "door":    "spruce_door",
                "window":  "glass_pane",
                "fence":   "spruce_fence",
                "light":   "lantern",
                "plaster": "snow_block",
            },
        },
        "districts": {
            "centre":      {"wall": "stone_bricks", "foundation": "stone_bricks"},
            "residential": {},
            "farming":     {"wall": "cobblestone"},
            "fishing":     {"wall": "spruce_planks", "foundation": "stone_bricks"},
            "forest":      {"wall": "packed_ice"},
        },
        "roads": {
            "main": {"variants": ["stone_bricks", "gravel"],    "weights": [0.65, 0.35]},
            "path": {"variants": ["gravel", "coarse_dirt"],     "weights": [0.60, 0.40]},
            "edge": "stone_brick_slab",
        },
    },

    # -----------------------------------------------------------------------
    # ARID — desert, dunes
    # -----------------------------------------------------------------------
    "ARID": {
        "structure": {
            "primary_wall":   {"variants": ["sandstone", "smooth_sandstone", "cut_sandstone"],
                               "weights":  [0.45, 0.35, 0.20]},
            "foundation":     "sandstone",
            "frame":          "stripped_acacia_log",
            "roof":           {"block": "sandstone", "stairs": "sandstone_stairs", "slab": "sandstone_slab"},
            "decor": {
                "door":    "acacia_door",
                "window":  "glass_pane",
                "fence":   "acacia_fence",
                "light":   ["lantern", "torch"],
                "plaster": "smooth_sandstone",
            },
        },
        "districts": {
            "centre":      {"wall": "smooth_sandstone", "foundation": "sandstone"},
            "residential": {},
            "farming":     {"wall": "sandstone", "floor": "sand"},
            "fishing":     {"wall": "sandstone",  "foundation": "sandstone"},
            "forest":      {"wall": "cut_sandstone"},
        },
        "roads": {
            "main": {"variants": ["sandstone", "smooth_sandstone"],  "weights": [0.60, 0.40]},
            "path": {"variants": ["sand", "coarse_dirt"],            "weights": [0.65, 0.35]},
            "edge": "sandstone_slab",
        },
    },

    # -----------------------------------------------------------------------
    # LUSH — jungle, swamp, mangrove, bamboo
    # -----------------------------------------------------------------------
    "LUSH": {
        "structure": {
            "primary_wall":   {"variants": ["mossy_stone_bricks", "mud_bricks", "cobblestone"],
                               "weights":  [0.45, 0.35, 0.20]},
            "foundation":     "cobblestone",
            "frame":          "jungle_log",
            "roof":           {"block": "oak_planks", "stairs": "oak_stairs", "slab": "oak_slab"},
            "decor": {
                "door":    "jungle_door",
                "window":  "glass_pane",
                "fence":   "jungle_fence",
                "light":   "lantern",
                "plaster": "moss_block",
            },
        },
        "districts": {
            "centre":      {"wall": "mossy_stone_bricks", "foundation": "cobblestone"},
            "residential": {},
            "farming":     {"wall": "mud_bricks", "floor": "coarse_dirt"},
            "fishing":     {"wall": "jungle_planks",  "foundation": "cobblestone"},
            "forest":      {"wall": "mossy_cobblestone"},
        },
        "roads": {
            "main": {"variants": ["mossy_cobblestone", "cobblestone"],   "weights": [0.55, 0.45]},
            "path": {"variants": ["coarse_dirt", "dirt"],                "weights": [0.60, 0.40]},
            "edge": "mossy_cobblestone_slab",
        },
    },

    # -----------------------------------------------------------------------
    # AQUATIC — ocean, river, beach
    # -----------------------------------------------------------------------
    "AQUATIC": {
        "structure": {
            "primary_wall":   {"variants": ["prismarine", "stone_bricks", "cobblestone"],
                               "weights":  [0.40, 0.35, 0.25]},
            "foundation":     "cobblestone",
            "frame":          "oak_log",
            "roof":           {"block": "oak_planks", "stairs": "oak_stairs", "slab": "oak_slab"},
            "decor": {
                "door":    "oak_door",
                "window":  "glass_pane",
                "fence":   "oak_fence",
                "light":   ["sea_lantern", "lantern"],
                "plaster": "prismarine_bricks",
            },
        },
        "districts": {
            "centre":      {"wall": "prismarine_bricks", "foundation": "stone_bricks"},
            "residential": {},
            "farming":     {"wall": "cobblestone"},
            "fishing":     {"wall": "oak_planks", "foundation": "prismarine"},
            "forest":      {"wall": "prismarine"},
        },
        "roads": {
            "main": {"variants": ["stone_bricks", "gravel"],    "weights": [0.60, 0.40]},
            "path": {"variants": ["gravel", "dirt_path"],       "weights": [0.55, 0.45]},
            "edge": "prismarine_slab",
        },
    },

    # -----------------------------------------------------------------------
    # SAVANNA — acacia/orange wood focus
    # -----------------------------------------------------------------------
    "SAVANNA": {
        "structure": {
            "primary_wall":   {"variants": ["orange_terracotta", "terracotta", "stone_bricks"],
                               "weights":  [0.40, 0.35, 0.25]},
            "foundation":     "stone_bricks",
            "frame":          "acacia_log",
            "roof":           {"block": "acacia_planks", "stairs": "acacia_stairs", "slab": "acacia_slab"},
            "decor": {
                "door":    "acacia_door",
                "window":  "glass_pane",
                "fence":   "acacia_fence",
                "light":   ["lantern", "torch"],
                "plaster": "yellow_terracotta",
            },
        },
        "districts": {
            "centre":      {"wall": "stone_bricks", "foundation": "stone_bricks"},
            "residential": {},
            "farming":     {"wall": "terracotta", "floor": "dirt"},
            "fishing":     {"wall": "acacia_planks", "foundation": "cobblestone"},
            "forest":      {"wall": "orange_terracotta"},
        },
        "roads": {
            "main": {"variants": ["terracotta", "stone_bricks"],  "weights": [0.55, 0.45]},
            "path": {"variants": ["dirt_path", "coarse_dirt"],    "weights": [0.70, 0.30]},
            "edge": "stone_brick_slab",
        },
    },

    # -----------------------------------------------------------------------
    # BADLANDS — terracotta/red sandstone focus
    # -----------------------------------------------------------------------
    "BADLANDS": {
        "structure": {
            "primary_wall":   {"variants": ["red_terracotta", "orange_terracotta", "brown_terracotta"],
                               "weights":  [0.45, 0.35, 0.20]},
            "foundation":     "red_sandstone",
            "frame":          "acacia_log",
            "roof":           {"block": "acacia_planks", "stairs": "acacia_stairs", "slab": "acacia_slab"},
            "decor": {
                "door":    "acacia_door",
                "window":  "glass_pane",
                "fence":   "acacia_fence",
                "light":   ["lantern", "torch"],
                "plaster": "yellow_terracotta",
            },
        },
        "districts": {
            "centre":      {"wall": "red_sandstone", "foundation": "red_sandstone"},
            "residential": {},
            "farming":     {"wall": "orange_terracotta", "floor": "coarse_dirt"},
            "fishing":     {"wall": "red_sandstone", "foundation": "cobblestone"},
            "forest":      {"wall": "brown_terracotta"},
        },
        "roads": {
            "main": {"variants": ["red_sandstone", "terracotta"],  "weights": [0.60, 0.40]},
            "path": {"variants": ["coarse_dirt", "sand"],          "weights": [0.60, 0.40]},
            "edge": "red_sandstone_slab",
        },
    },

    # -----------------------------------------------------------------------
    # CHERRY_GROVE — pink/oriental aesthetic (MC 1.20+)
    # -----------------------------------------------------------------------
    "CHERRY_GROVE": {
        "structure": {
            "primary_wall":   {"variants": ["stone_bricks", "calcite", "cobblestone"],
                               "weights":  [0.50, 0.30, 0.20]},
            "foundation":     "stone_bricks",
            "frame":          "oak_log",
            "roof":           {"block": "oak_planks", "stairs": "oak_stairs", "slab": "oak_slab"},
            "decor": {
                "door":    "oak_door",
                "window":  "glass_pane",
                "fence":   "oak_fence",
                "light":   "lantern",
                "plaster": "calcite",
            },
        },
        "districts": {
            "centre":      {"wall": "calcite", "foundation": "stone_bricks"},
            "residential": {},
            "farming":     {"wall": "cobblestone"},
            "fishing":     {"wall": "oak_planks", "foundation": "cobblestone"},
            "forest":      {"wall": "stone_bricks"},
        },
        "roads": {
            "main": {"variants": ["stone_bricks", "cobblestone"],  "weights": [0.60, 0.40]},
            "path": {"variants": ["dirt_path", "coarse_dirt"],     "weights": [0.70, 0.30]},
            "edge": "stone_brick_slab",
        },
    },
}
