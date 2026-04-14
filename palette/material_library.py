"""Global Material Library for Procedural Building Generation
- Supports weighted primary wall selection
- Fully categorized by Archetype (TEMPERATE, FROZEN, ARID, LUSH, AQUATIC)
- Includes district-specific overrides
- All decor entries are lists to avoid string-slicing bugs
-adds road materials per archetype with main/path distinction
"""

MATERIAL_LIBRARY = {
    "TEMPERATE": {
        "structure": {
            "primary_wall": {"variants": ["stone_bricks", "cobblestone", "andesite","dark_oak_planks", "birch_planks", "white_wool"], "weights": [0.3, 0.2, 0.2, 0.1, 0.1, 0.1]},
            "foundation": "cobblestone",
            "accent": ["stripped_oak_log", "oak_log", "birch_log", "dark_oak_log"],
            "roof": {
                "variants": [
                    {
                        "label": "dark_oak",
                        "block": "dark_oak_planks", 
                        "stairs": "dark_oak_stairs", 
                        "slab": "dark_oak_slab"
                    },
                    {
                        "label": "spruce",
                        "block": "spruce_planks", 
                        "stairs": "spruce_stairs", 
                        "slab": "spruce_slab"
                    },
                    {
                        "label": "deepslate",
                        "block": "deepslate_tiles", 
                        "stairs": "deepslate_tile_stairs", 
                        "slab": "deepslate_tile_slab"
                    }
                ],
                "weights": [0.2, 0.3, 0.5]
            },
            "decor": {
                "chimney": ["bricks", "cobblestone"],
                "light": ["lantern"],
                "window": ["glass_pane"]
            }
        },
        "districts": {
            "fishing": {"dock": ["oak_slab"], "barrel": ["barrel"]},
            "blacksmith": {"hearth": ["blast_furnace"], "floor": ["stone_brick_tiles"]},
            "centre": {"plaza": ["polished_andesite"], "monument": ["smooth_stone"]}
        },
        "roads": {
            "main": {"variants": ["stone_bricks", "cobblestone"], "weights": [0.7, 0.3]},
            "path": {"variants": ["dirt_path", "gravel"], "weights": [0.8, 0.2]},
            "edge": "cobblestone_slab"
        }
    },
    "FROZEN": {
        "structure": {
            "primary_wall": {"variants": ["deepslate_bricks", "cobblestone"], "weights": [0.7, 0.3]},
            "foundation": "deepslate",
            "accent": ["stripped_spruce_log", "spruce_log"],
            "roof": {
                "variants": [
                    {"label": "spruce", "block": "spruce_planks", "stairs": "spruce_stairs", "slab": "spruce_slab"},
                    {"label": "dark_oak", "block": "dark_oak_planks", "stairs": "dark_oak_stairs", "slab": "dark_oak_slab"}
                ],
                "weights": [0.6, 0.4]
            },
            "decor": {
                "chimney": ["basalt", "cobblestone"],
                "light": ["soul_lantern"],
                "window": ["light_blue_stained_glass"]
            }
        },
        "districts": {
            "fishing": {"dock": ["spruce_slab"], "barrel": ["barrel"]},
            "blacksmith": {"hearth": ["blast_furnace"], "floor": ["deepslate_tiles"]},
            "centre": {"plaza": ["polished_deepslate"], "monument": ["blue_ice"]}
        },
        "roads": {
            "main": {"variants": ["deepslate_bricks", "polished_andesite"], "weights": [0.6, 0.4]},
            "path": {"variants": ["packed_ice", "snow_block"], "weights": [0.5, 0.5]},
            "edge": "stone_brick_slab"
        }
    },
    "ARID": {  # Desert / Savanna / Badlands
        "structure": {
            "primary_wall": {"variants": ["sandstone", "smooth_sandstone", "cut_sandstone"], "weights": [0.6, 0.3, 0.1]},
            "foundation": "sandstone",
            "accent": ["acacia_log", "stripped_acacia_log"],
            "roof": {
                "variants": [
                    {"label": "acacia", "block": "acacia_planks", "stairs": "acacia_stairs", "slab": "acacia_slab"},
                    {"label": "jungle", "block": "jungle_planks", "stairs": "jungle_stairs", "slab": "jungle_slab"},
                    {"label": "smooth_stone", "block": "smooth_stone", "stairs": "stone_stairs", "slab": "stone_slab"}
                ],
                "weights": [0.6, 0.2, 0.2]
            },
            "decor": {
                "chimney": ["sandstone", "smooth_sandstone"],
                "light": ["lantern"],
                "window": ["glass_pane"]
            }
        },
        "districts": {
            "fishing": {"dock": ["acacia_slab"], "barrel": ["barrel"]},
            "blacksmith": {"hearth": ["blast_furnace"], "floor": ["sandstone_tiles"]},
            "centre": {"plaza": ["polished_sandstone"], "monument": ["cut_sandstone"]}
        },
        "roads": {
            "main": {"variants": ["cut_sandstone", "smooth_sandstone"], "weights": [0.7, 0.3]},
            "path": {"variants": ["smooth_sandstone", "dirt_path"], "weights": [0.7, 0.3]},
            "edge": "sandstone_slab"
        }
    },
    "LUSH": {  # Jungle / Swamp / Mangrove
        "structure": {
            "primary_wall": {"variants": ["mossy_stone_bricks", "mossy_cobblestone", "mud_bricks"], "weights": [0.4, 0.4, 0.2]},
            "foundation": "cobblestone",
            "accent": ["jungle_log", "stripped_jungle_log", "mangrove_log"],
            "roof": {
                "variants": [
                    {"label": "jungle", "block": "jungle_planks", "stairs": "jungle_stairs", "slab": "jungle_slab"},
                    {"label": "mangrove", "block": "mangrove_planks", "stairs": "mangrove_stairs", "slab": "mangrove_slab"},
                    {"label": "mud_brick", "block": "mud_bricks", "stairs": "mud_brick_stairs", "slab": "mud_brick_slab"}
                ],
                "weights": [0.3, 0.4, 0.3]
            },
            "decor": {
                "chimney": ["mossy_cobblestone", "mud_bricks"],
                "light": ["lantern"],
                "window": ["glass_pane"]
            }
        },
        "districts": {
            "fishing": {"dock": ["spruce_slab"], "barrel": ["barrel"]},
            "blacksmith": {"hearth": ["blast_furnace"], "floor": ["mossy_cobblestone"]},
            "centre": {"plaza": ["polished_andesite"], "monument": ["moss_block"]}
        },
        "roads": {
            "main": {"variants": ["mossy_stone_bricks", "mossy_cobblestone"], "weights": [0.6, 0.4]},
            "path": {"variants": ["mud", "dirt_path"], "weights": [0.7, 0.3]},
            "edge": "mossy_cobblestone_slab"
        }
    },
    "AQUATIC": {  # Ocean / River / Deep Sea
        "structure": {
            "primary_wall": {"variants": ["prismarine_bricks", "dark_prismarine"], "weights": [0.7, 0.3]},
            "foundation": "prismarine",
            "accent": ["stripped_oak_log", "oak_log"],
            "roof": {
                "variants": [
                    {"label": "dark_prismarine", "block": "dark_prismarine", "stairs": "dark_prismarine_stairs", "slab": "dark_prismarine_slab"},
                    {"label": "prismarine_brick", "block": "prismarine_bricks", "stairs": "prismarine_brick_stairs", "slab": "prismarine_brick_slab"}
                ],
                "weights": [0.5, 0.5]
            },
            "decor": {
                "chimney": ["oak_log", "stripped_oak_log"],
                "light": ["sea_lantern"],
                "window": ["glass_pane"]
            }
        },
        "districts": {
            "fishing": {"dock": ["spruce_slab"], "barrel": ["barrel"]},
            "blacksmith": {"hearth": ["blast_furnace"], "floor": ["prismarine_tiles"]},
            "centre": {"plaza": ["prismarine"], "monument": ["sea_lantern"]}
        },
        "roads": {
            "main": {"variants": ["oak_planks", "spruce_planks"], "weights": [0.8, 0.2]},
            "path": {"variants": ["oak_slab", "spruce_slab"], "weights": [0.9, 0.1]},
            "edge": "oak_fence"
        }
    },
    "SAVANNA": {
        "structure": {
            "primary_wall": {"variants": ["orange_terracotta", "yellow_terracotta", "coarse_dirt"], "weights": [0.5, 0.3, 0.2]},
            "foundation": "coarse_dirt",
            "accent": ["acacia_log", "stripped_acacia_log"],
            "roof": {
                "variants": [
                    {"label": "acacia", "block": "acacia_planks", "stairs": "acacia_stairs", "slab": "acacia_slab"},
                    {"label": "stone_brick", "block": "stone_bricks", "stairs": "stone_brick_stairs", "slab": "stone_brick_slab"}
                ],
                "weights": [0.7, 0.3]
            },
            "decor": {
                "chimney": ["terracotta"],
                "light": ["lantern"],
                "window": ["glass_pane"]
            }
        },
        "districts": {
            "fishing": {"dock": ["acacia_slab"], "barrel": ["barrel"]},
            "blacksmith": {"hearth": ["blast_furnace"], "floor": ["terracotta_tiles"]},
            "centre": {"plaza": ["polished_terracotta"], "monument": ["cut_terracotta"]}
        },
        "roads": {
            "main": {"variants": ["stone_bricks", "cobblestone"], "weights": [0.8, 0.2]},
            "path": {"variants": ["coarse_dirt", "dirt_path"], "weights": [0.6, 0.4]},
            "edge": "acacia_slab"
        }
    },
    "BADLANDS": {
        "structure": {
            "primary_wall": {"variants": ["red_sandstone", "terracotta", "brown_terracotta"], "weights": [0.4, 0.4, 0.2]},
            "foundation": "red_sandstone",
            "accent": ["dark_oak_log", "stripped_dark_oak_log"], # Dark wood looks great against red sand
            "roof": {
                "variants": [
                    {"label": "dark_oak", "block": "dark_oak_planks", "stairs": "dark_oak_stairs", "slab": "dark_oak_slab"},
                    {"label": "red_sandstone", "block": "red_sandstone", "stairs": "red_sandstone_stairs", "slab": "red_sandstone_slab"}
                ],
                "weights": [0.3, 0.7]
            },
            "decor": {
                "chimney": ["red_sandstone_wall"],
                "light": ["lantern"],
                "window": ["orange_stained_glass"]
            }
        },
        "districts": {
            "fishing": {"dock": ["dark_oak_slab"], "barrel": ["barrel"]},
            "blacksmith": {"hearth": ["blast_furnace"], "floor": ["red_nether_bricks"]},
            "centre": {"plaza": ["smooth_red_sandstone"], "monument": ["gold_block"]}
        },
        "roads": {
            "main": {"variants": ["red_sandstone", "polished_granite"], "weights": [0.3, 0.7]},
            "path": {"variants": ["red_terracotta", "coarse_dirt"], "weights": [0.3, 0.7]},
            "edge": "red_sandstone_slab"
        }
    }
}