"""
data/material_families.py
--------------------------
Static material data consumed by planning/palette_mapper.py.

Kept in data/ because these are pure lookup tables with no logic — they
describe *what exists* in each biome, not how to choose between options.

Relationship to data/biome_palettes.py
---------------------------------------
biome_palettes.py  — curated, hand-tuned final palettes used directly by
                     structure builders when no per-district variation is needed.
material_families  — raw ingredient pools used by PaletteMapper to generate
                     per-district palettes with coherence principles applied.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Material families — blocks that belong together per biome
# ---------------------------------------------------------------------------

MATERIAL_FAMILIES: dict[str, dict[str, list[str]]] = {
    "plains": {
        "primary_wood":    ["oak"],
        "secondary_wood":  ["dark_oak"],
        "primary_stone":   ["cobblestone"],
        "secondary_stone": ["stone_bricks", "smooth_stone"],
        "accent_blocks":   ["terracotta", "stripped_oak_log", "hay_block"],
        "detail_blocks":   ["oak_fence", "oak_door", "flower_pot"],
    },
    "forest": {
        "primary_wood":    ["oak"],
        "secondary_wood":  ["dark_oak", "spruce"],
        "primary_stone":   ["mossy_cobblestone"],
        "secondary_stone": ["stone_bricks", "moss_block"],
        "accent_blocks":   ["dark_oak_log", "stripped_oak_log", "oak_log"],
        "detail_blocks":   ["hanging_roots", "moss_carpet", "oak_fence"],
    },
    "taiga": {
        "primary_wood":    ["spruce"],
        "secondary_wood":  ["dark_oak"],
        "primary_stone":   ["stone_bricks"],
        "secondary_stone": ["cobblestone"],
        "accent_blocks":   ["stripped_spruce_log", "snow", "powder_snow"],
        "detail_blocks":   ["spruce_fence", "lantern", "spruce_door"],
    },
    "snowy_plains": {
        "primary_wood":    ["spruce"],
        "secondary_wood":  ["oak"],
        "primary_stone":   ["stone_bricks"],
        "secondary_stone": ["snow_block", "powder_snow"],
        "accent_blocks":   ["blue_ice", "ice", "stripped_spruce_log"],
        "detail_blocks":   ["lantern", "spruce_fence"],
    },
    "jungle": {
        "primary_wood":    ["jungle_wood"],
        "secondary_wood":  ["oak", "dark_oak"],
        "primary_stone":   ["mossy_stone_bricks"],
        "secondary_stone": ["mossy_cobblestone", "cobblestone"],
        "accent_blocks":   ["terracotta", "stripped_jungle_log", "jungle_wood_log"],
        "detail_blocks":   ["vine", "jungle_fence", "jungle_door"],
    },
    "desert": {
        "primary_wood":    ["oak"],
        "secondary_wood":  ["dark_oak"],
        "primary_stone":   ["sandstone"],
        "secondary_stone": ["smooth_sandstone", "red_sand"],
        "accent_blocks":   ["terracotta", "chiseled_sandstone", "red_terracotta"],
        "detail_blocks":   ["oak_fence", "oak_door", "dead_bush"],
    },
    "savanna": {
        "primary_wood":    ["acacia"],
        "secondary_wood":  ["oak"],
        "primary_stone":   ["cobblestone"],
        "secondary_stone": ["smooth_sandstone"],
        "accent_blocks":   ["orange_terracotta", "acacia_log", "acacia_fence"],
        "detail_blocks":   ["acacia_door", "acacia_fence"],
    },
    "mountains": {
        "primary_wood":    ["spruce", "dark_oak"],
        "secondary_wood":  ["oak"],
        "primary_stone":   ["stone_bricks"],
        "secondary_stone": ["cracked_stone_bricks", "cobblestone"],
        "accent_blocks":   ["stripped_dark_oak_log", "blackstone", "deepslate_bricks"],
        "detail_blocks":   ["iron_bars", "lantern"],
    },
    "windswept_hills": {
        "primary_wood":    ["spruce"],
        "secondary_wood":  ["dark_oak"],
        "primary_stone":   ["stone_bricks"],
        "secondary_stone": ["cobblestone", "gravel"],
        "accent_blocks":   ["stripped_spruce_log", "gray_concrete"],
        "detail_blocks":   ["lantern", "iron_bars"],
    },
}

# ---------------------------------------------------------------------------
# Color temperature classification
# ---------------------------------------------------------------------------

WARM_WOODS:    list[str] = ["oak", "dark_oak", "acacia", "jungle_wood"]
COOL_WOODS:    list[str] = ["spruce", "birch"]
WARM_STONES:   list[str] = ["sandstone", "smooth_sandstone", "terracotta", "red_terracotta"]
COOL_STONES:   list[str] = ["stone_bricks", "cobblestone", "deepslate_bricks", "blackstone"]
NEUTRAL_STONES: list[str] = ["mossy_cobblestone", "mossy_stone_bricks", "moss_block"]

# ---------------------------------------------------------------------------
# Value (brightness) classification
# ---------------------------------------------------------------------------

BLOCK_VALUES: dict[str, str] = {
    # Light
    "snow":             "light",
    "powder_snow":      "light",
    "birch_log":        "light",
    "sand":             "light",
    "sandstone":        "light",
    "smooth_sandstone": "light",
    "smooth_stone":     "light",
    "white_concrete":   "light",
    "blue_ice":         "light",
    # Medium
    "oak":               "medium",
    "oak_planks":        "medium",
    "oak_log":           "medium",
    "jungle_wood":       "medium",
    "acacia":            "medium",
    "acacia_log":        "medium",
    "terracotta":        "medium",
    "stone_bricks":      "medium",
    "cobblestone":       "medium",
    "mossy_cobblestone": "medium",
    "moss_block":        "medium",
    "hay_block":         "medium",
    # Dark
    "dark_oak":             "dark",
    "dark_oak_log":         "dark",
    "spruce":               "dark",
    "spruce_log":           "dark",
    "blackstone":           "dark",
    "deepslate_bricks":     "dark",
    "mossy_stone_bricks":   "dark",
    "stripped_spruce_log":  "dark",
    "stripped_dark_oak_log": "dark",
    "gray_concrete":        "dark",
}

# ---------------------------------------------------------------------------
# Decoration pools per biome
# Used by generators that place decorative props after structures are built.
# ---------------------------------------------------------------------------

DECO_POOLS: dict[str, list[str]] = {
    "plains":          ["flower_pot", "hay_block", "barrel", "lantern"],
    "forest":          ["mushroom_stem", "composter", "flower_pot", "moss_carpet"],
    "taiga":           ["lantern", "barrel", "sweet_berry_bush", "spruce_fence"],
    "snowy_plains":    ["lantern", "blue_ice", "barrel", "spruce_fence"],
    "savanna":         ["dried_kelp_block", "hay_block", "flower_pot", "acacia_fence"],
    "jungle":          ["vine", "bamboo", "flower_pot", "jungle_fence"],
    "desert":          ["dead_bush", "sand", "chiseled_sandstone", "cactus"],
    "mountains":       ["lantern", "iron_bars", "chiseled_stone_bricks", "deepslate_tiles"],
    "windswept_hills": ["lantern", "iron_bars", "cobblestone_wall", "gravel"],
}

# ---------------------------------------------------------------------------
# Biome integer ID → canonical name
#
# These are legacy numeric IDs from older Minecraft versions / world-analysis
# output.  String biome IDs (e.g. "minecraft:plains") are handled separately
# in PaletteMapper._biome_id_to_name() by stripping the namespace prefix.
# ---------------------------------------------------------------------------

BIOME_ID_MAP: dict[int, str] = {
    1:  "plains",
    4:  "forest",
    5:  "taiga",
    2:  "desert",
    35: "savanna",
    12: "snowy_plains",
    21: "jungle",
    3:  "mountains",
    34: "windswept_hills",
}