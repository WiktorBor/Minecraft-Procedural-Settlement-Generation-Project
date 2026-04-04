"""
data/palette_system.py
-----------------------
Biome-local, stone-first palette generation with per-district memory.

Key improvements over the previous PaletteMapper:
  1. Local biome detection  — samples the biome at the exact district-centre
                              (x, z) rather than averaging across the whole district.
  2. Stone-first materials  — primary material is always a stone type; wood is
                              secondary/decorative.
  3. District memory        — each district locks its primary stone on first use and
                              tracks per-building history for anti-clustering.

Output format is the same BiomePalette TypedDict used everywhere else so no
builder changes are required.
"""
from __future__ import annotations

import logging
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List

from data.biome_palettes import BiomePalette

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Material families
# ---------------------------------------------------------------------------

MATERIAL_FAMILIES: Dict[str, dict] = {
    "plains": {
        "primary_stone":   ["stone_bricks", "cobblestone"],
        "secondary_stone": ["mossy_cobblestone", "andesite"],
        "accent_stone":    ["yellow_terracotta", "red_terracotta"],
        "wood_trim":       "oak",
        "wood_accent":     ["oak_log", "oak_fence"],
        "roof_material":   "oak",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "dirt_path",
    },
    "forest": {
        "primary_stone":   ["mossy_cobblestone", "stone_bricks"],
        "secondary_stone": ["moss_block", "cobblestone"],
        "accent_stone":    ["dark_oak_log"],
        "wood_trim":       "oak",
        "wood_accent":     ["dark_oak_log", "dark_oak_fence"],
        "roof_material":   "dark_oak",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "coarse_dirt",
    },
    "taiga": {
        "primary_stone":   ["stone_bricks", "packed_ice"],
        "secondary_stone": ["ice", "cobblestone"],
        "accent_stone":    ["snow_block", "blue_ice"],
        "wood_trim":       "spruce",
        "wood_accent":     ["spruce_log", "spruce_fence"],
        "roof_material":   "spruce",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "coarse_dirt",
    },
    "snowy_plains": {
        "primary_stone":   ["packed_ice", "stone_bricks"],
        "secondary_stone": ["snow_block", "cobblestone"],
        "accent_stone":    ["blue_ice", "powder_snow"],
        "wood_trim":       "spruce",
        "wood_accent":     ["spruce_log", "spruce_fence"],
        "roof_material":   "spruce",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "dirt_path",
    },
    "desert": {
        "primary_stone":   ["sandstone", "smooth_sandstone"],
        "secondary_stone": ["orange_terracotta", "terracotta"],
        "accent_stone":    ["chiseled_sandstone", "cut_sandstone"],
        "wood_trim":       "acacia",
        "wood_accent":     ["acacia_log", "acacia_fence"],
        "roof_material":   "sandstone",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "sand",
    },
    "jungle": {
        "primary_stone":   ["mossy_stone_bricks", "mud"],
        "secondary_stone": ["moss_block", "mossy_cobblestone"],
        "accent_stone":    ["jungle_log"],
        "wood_trim":       "jungle",
        "wood_accent":     ["jungle_log", "jungle_fence"],
        "roof_material":   "dark_oak",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "coarse_dirt",
    },
    "mountains": {
        "primary_stone":   ["stone_bricks", "deepslate_bricks"],
        "secondary_stone": ["blackstone", "cobblestone"],
        "accent_stone":    ["gray_concrete", "deepslate_tiles"],
        "wood_trim":       "dark_oak",
        "wood_accent":     ["dark_oak_log", "dark_oak_fence"],
        "roof_material":   "dark_oak",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "dirt_path",
    },
    "rocky_shores": {
        "primary_stone":   ["cobblestone", "stone_bricks"],
        "secondary_stone": ["andesite", "mossy_cobblestone"],
        "accent_stone":    ["cyan_terracotta"],
        "wood_trim":       "spruce",
        "wood_accent":     ["spruce_log", "spruce_fence"],
        "roof_material":   "spruce",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "dirt_path",
    },
    "savanna": {
        "primary_stone":   ["terracotta", "orange_terracotta"],
        "secondary_stone": ["sand", "red_terracotta"],
        "accent_stone":    ["acacia_log", "yellow_terracotta"],
        "wood_trim":       "acacia",
        "wood_accent":     ["acacia_log", "acacia_fence"],
        "roof_material":   "acacia",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "dirt_path",
    },
    "swamp": {
        "primary_stone":   ["mud", "mossy_cobblestone"],
        "secondary_stone": ["moss_block", "cobblestone"],
        "accent_stone":    ["dark_oak_log"],
        "wood_trim":       "dark_oak",
        "wood_accent":     ["dark_oak_log", "dark_oak_fence"],
        "roof_material":   "dark_oak",
        "smoke":           "soul_campfire",
        "moss":            "moss_carpet",
        "path":            "coarse_dirt",
    },
    "deep_ocean": {
        "primary_stone":   ["prismarine", "dark_prismarine"],
        "secondary_stone": ["prismarine_bricks", "stone_bricks"],
        "accent_stone":    ["dark_prismarine", "sea_lantern"],
        "wood_trim":       "oak",
        "wood_accent":     ["oak_log", "oak_fence"],
        "roof_material":   "oak",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "dirt_path",
    },
    "badlands": {
        "primary_stone":   ["red_terracotta", "orange_terracotta"],
        "secondary_stone": ["yellow_terracotta", "brown_terracotta"],
        "accent_stone":    ["orange_terracotta", "red_concrete"],
        "wood_trim":       "acacia",
        "wood_accent":     ["acacia_log", "acacia_fence"],
        "roof_material":   "acacia",
        "smoke":           "campfire",
        "moss":            "moss_carpet",
        "path":            "sand",
    },
    # aliases
    "snowy_mountains": {"parent": "mountains"},
    "wooded_badlands": {"parent": "badlands"},
    "badlands_plateau": {"parent": "badlands"},
    "jungle_edge":     {"parent": "jungle"},
    "jungle_hills":    {"parent": "jungle"},
}

BIOME_ID_MAPPING: Dict[int, str] = {
    0: "deep_ocean",
    1: "plains",
    2: "desert",
    3: "mountains",
    4: "forest",
    5: "taiga",
    6: "swamp",
    10: "snowy_plains",
    12: "taiga",
    13: "snowy_mountains",
    14: "snowy_plains",
    15: "badlands",
    16: "wooded_badlands",
    17: "badlands_plateau",
    19: "forest",
    20: "jungle",
    21: "jungle_edge",
    22: "jungle_hills",
    23: "jungle_edge",
    24: "swamp",
    27: "rocky_shores",
    28: "rocky_shores",
    29: "savanna",
    30: "savanna",
    31: "savanna",
    35: "savanna",
    149: "jungle",
}


# ---------------------------------------------------------------------------
# District memory
# ---------------------------------------------------------------------------

@dataclass
class DistrictMemory:
    """Locks core materials per district and tracks anti-clustering history."""
    district_id:    int
    biome_family:   str
    primary_stone:  str
    secondary_stone: str
    wood_trim:      str
    roof_block:     str
    history: deque = field(default_factory=lambda: deque(maxlen=5))

    def record(self, stone: str) -> None:
        self.history.append(stone)

    def is_overused(self, material: str, threshold: int = 3) -> bool:
        return self.history.count(material) >= threshold

    def alternatives(self, candidates: List[str]) -> List[str]:
        return [c for c in candidates if c not in self.history]


# ---------------------------------------------------------------------------
# PaletteSystem
# ---------------------------------------------------------------------------

class PaletteSystem:
    """
    Stone-first palette selection with local biome detection and district memory.

    Usage (replaces PaletteMapper.generate()):
        system   = PaletteSystem()
        palettes = system.generate(analysis, districts)
        # → dict[int, BiomePalette]
    """

    def __init__(self) -> None:
        self._memories: Dict[int, DistrictMemory] = {}

    # ------------------------------------------------------------------
    # Public API — matches the shape of PaletteMapper.generate()
    # ------------------------------------------------------------------

    def generate(self, analysis, districts) -> Dict[int, BiomePalette]:
        """Generate a BiomePalette for every district and return them."""
        palettes: Dict[int, BiomePalette] = {}
        for idx, dtype in districts.types.items():
            district = districts.district_list[idx]
            cx = int(district.center_x)
            cz = int(district.center_z)
            palettes[idx] = self.create_palette(cx, cz, idx, analysis)
        return palettes

    # ------------------------------------------------------------------
    # Core palette creation
    # ------------------------------------------------------------------

    def create_palette(
        self,
        x: int,
        z: int,
        district_id: int,
        analysis=None,
    ) -> BiomePalette:
        """Create a BiomePalette for a structure at world position (x, z)."""
        biome_name  = self._local_biome(analysis, x, z)
        family      = self._resolve_family(biome_name)
        memory      = self._get_or_create_memory(district_id, biome_name, family)

        primary   = self._pick_primary(family, memory)
        secondary = self._pick_secondary(family, memory, primary)
        accent    = random.choice(family["accent_stone"])
        wood      = memory.wood_trim
        roof_mat  = memory.roof_block

        memory.record(primary)

        def mc(block: str) -> str:
            return block if block.startswith("minecraft:") else f"minecraft:{block}"

        def wood_block(suffix: str) -> str:
            base = f"{wood}_{suffix}"
            return mc(base)

        def roof_block(suffix: str) -> str:
            # sandstone/deepslate don't follow the normal _stairs/_slab pattern
            special = {
                "sandstone":       {"stairs": "sandstone_stairs",       "slab": "sandstone_slab"},
                "smooth_sandstone":{"stairs": "sandstone_stairs",       "slab": "sandstone_slab"},
                "deepslate_bricks":{"stairs": "deepslate_brick_stairs", "slab": "deepslate_brick_slab"},
            }
            if roof_mat in special:
                return mc(special[roof_mat][suffix])
            return mc(f"{roof_mat}_{suffix}")

        palette: BiomePalette = {
            # Core structure — stone-first
            "wall":           mc(primary),
            "wall_secondary": mc(secondary),
            "foundation":     mc(secondary),
            "floor":          wood_block("planks"),
            "accent":         mc(accent),
            "accent_beam":    mc(f"stripped_{wood}_log"),

            # Roof
            "roof":           roof_block("stairs"),
            "roof_slab":      roof_block("slab"),
            "ceiling_slab":   wood_block("slab"),

            # Openings
            "door":           wood_block("door"),
            "window":         "minecraft:glass_pane",
            "fence":          wood_block("fence"),

            # Lighting
            "light":          "minecraft:lantern",
            "interior_light": "minecraft:lantern",

            # Environment
            "path":           mc(family.get("path", "dirt_path")),
            "path_edge":      "minecraft:coarse_dirt",
            "path_slab":      wood_block("slab"),
            "smoke":          mc(family.get("smoke", "campfire")),
            "moss":           mc(family.get("moss", "moss_carpet")),
            "banner":         "minecraft:white_banner",
        }

        logger.debug(
            "Palette district=%d  biome=%s  primary=%s  secondary=%s  wood=%s",
            district_id, biome_name, primary, secondary, wood,
        )
        return palette

    # ------------------------------------------------------------------
    # Biome resolution
    # ------------------------------------------------------------------

    def _local_biome(self, analysis, x: int, z: int) -> str:
        if analysis is None or not hasattr(analysis, "best_area"):
            return "plains"
        try:
            li, lj = analysis.best_area.world_to_index(x, z)
            h, w   = analysis.biomes.shape
            if not (0 <= li < h and 0 <= lj < w):
                return self._nearest_biome(analysis, li, lj)
            raw = analysis.biomes[li, lj]
            name = (
                raw.replace("minecraft:", "").lower()
                if isinstance(raw, str)
                else BIOME_ID_MAPPING.get(int(raw))
            )
            if name and name in MATERIAL_FAMILIES:
                return name
            return self._nearest_biome(analysis, li, lj)
        except Exception as exc:
            logger.warning("Biome detection failed at (%d,%d): %s", x, z, exc)
            return "plains"

    def _nearest_biome(self, analysis, li: int, lj: int) -> str:
        grid   = analysis.biomes
        h, w   = grid.shape
        best   = {}
        for radius in range(1, min(11, h // 2, w // 2) + 1):
            for di in range(-radius, radius + 1):
                for dj in range(-radius, radius + 1):
                    ni, nj = li + di, lj + dj
                    if not (0 <= ni < h and 0 <= nj < w):
                        continue
                    raw  = grid[ni, nj]
                    name = (
                        raw.replace("minecraft:", "").lower()
                        if isinstance(raw, str)
                        else BIOME_ID_MAPPING.get(int(raw))
                    )
                    if name and name in MATERIAL_FAMILIES:
                        dist = (di ** 2 + dj ** 2) ** 0.5
                        best[name] = best.get(name, 0) + 1.0 / (dist + 1)
            if best:
                return max(best, key=best.__getitem__)
        return "plains"

    def _resolve_family(self, biome_name: str) -> dict:
        visited = set()
        name    = biome_name
        while name not in visited:
            visited.add(name)
            fam = MATERIAL_FAMILIES.get(name)
            if fam is None:
                return MATERIAL_FAMILIES["plains"]
            if "parent" in fam:
                name = fam["parent"]
            else:
                return fam
        return MATERIAL_FAMILIES["plains"]

    # ------------------------------------------------------------------
    # District memory
    # ------------------------------------------------------------------

    def _get_or_create_memory(
        self, district_id: int, biome_name: str, family: dict
    ) -> DistrictMemory:
        if district_id not in self._memories:
            self._memories[district_id] = DistrictMemory(
                district_id    = district_id,
                biome_family   = biome_name,
                primary_stone  = random.choice(family["primary_stone"]),
                secondary_stone= random.choice(family["secondary_stone"]),
                wood_trim      = family["wood_trim"],
                roof_block     = family["roof_material"],
            )
        return self._memories[district_id]

    # ------------------------------------------------------------------
    # Material selection
    # ------------------------------------------------------------------

    def _pick_primary(self, family: dict, memory: DistrictMemory) -> str:
        stone = memory.primary_stone
        if memory.is_overused(stone, threshold=3):
            alts = memory.alternatives(family["primary_stone"])
            if alts:
                stone = random.choice(alts)
        return stone

    def _pick_secondary(
        self, family: dict, memory: DistrictMemory, primary: str
    ) -> str:
        candidates = [s for s in family["secondary_stone"] if s != primary]
        if not candidates:
            candidates = family["secondary_stone"]
        alts = memory.alternatives(candidates)
        return random.choice(alts if alts else candidates)
