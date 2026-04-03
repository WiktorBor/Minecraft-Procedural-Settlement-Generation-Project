from __future__ import annotations
import random
from typing import Dict, List
from dataclasses import dataclass
from collections import deque
import logging

logger = logging.getLogger(__name__)
"""
BIOME → DISTRICT → [PRIMARY STONE, SECONDARY STONE, WOOD TRIM, ACCENTS]
1. Uses LOCAL biome materials (upgraded from district average)
2. Prioritizes STONE (medieval architecture)
3. Covers ALL Minecraft terrains

Workflow: Get building location → Detect local biome → Apply district theme → 
Select materials from biome family → Apply anti-clustering → Return palette
"""

# Each biome has STONE-PRIMARY design with wood as secondary/decorative
# biome_name -> {primary_stone, secondary_stone, accent_blocks, wood_trim, roofing}
MATERIAL_FAMILIES = {
    "plains": {
        "primary_stone": ["stone_bricks", "cobblestone"],
        "secondary_stone": ["mossy_cobblestone", "gravel"],
        "accent_stone": ["yellow_terracotta", "red_terracotta"],
        "wood_trim": "oak",  # Primary wood for this biome
        "wood_accent": ["oak_log", "oak_fence"],
        "roof_material": "oak",
        "description": "Medieval farmland with stone foundations",
        "smoke":"minecraft:campfire"
    },
    
    "forest": {
        "primary_stone": ["mossy_cobblestone", "stone_bricks"],
        "secondary_stone": ["moss_block", "cobblestone"],
        "accent_stone": ["dark_oak_log"],  # Stone-quality accent!
        "wood_trim": "oak",
        "wood_accent": ["dark_oak_log", "dark_oak_fence"],
        "roof_material": "dark_oak",
        "description": "Forest settlements with moss-covered stone",
        "smoke":"minecraft:campfire"
    },
    
    "taiga": {
        "primary_stone": ["stone_bricks", "packed_ice"],
        "secondary_stone": ["ice", "cobblestone"],
        "accent_stone": ["snow_block", "blue_ice"],
        "wood_trim": "spruce",
        "wood_accent": ["spruce_log", "spruce_fence"],
        "roof_material": "spruce",
        "description": "Snowy alpine stone structures"
    },
    "snowy_mountains": {"parent": "mountains"},
    "snowy_plains": {
        "primary_stone": ["packed_ice", "ice"],
        "secondary_stone": ["snow_block", "stone_bricks"],
        "accent_stone": ["blue_ice", "powder_snow"],
        "wood_trim": "spruce",
        "wood_accent": ["spruce_log", "spruce_fence"],
        "roof_material": "spruce",
        "description": "Tundra-like frozen settlements",
        "smoke":"minecraft:campfire"
    },
    
    "desert": {
        "primary_stone": ["sandstone", "smooth_sandstone"],
        "secondary_stone": ["orange_terracotta", "terracotta"],
        "accent_stone": ["chiseled_sandstone", "cut_sandstone"],
        "wood_trim": "acacia",
        "wood_accent": ["acacia_log", "acacia_fence"],
        "roof_material": "sandstone",
        "description": "Arid desert with sandstone architecture",
        "smoke":"minecraft:campfire"
    },
    
    "jungle": {
        "primary_stone": ["mossy_stone_bricks", "mud"],
        "secondary_stone": ["moss_block", "mossy_cobblestone"],
        "accent_stone": ["jungle_log", "vine"],  # Stone-quality
        "wood_trim": "jungle",
        "wood_accent": ["jungle_log", "jungle_fence"],
        "roof_material": "dark_oak",
        "description": "Tropical jungle temples with moss and vines",
        "smoke":"minecraft:campfire"
    },
    
    "mountains": {
        "primary_stone": ["stone_bricks", "deepslate_bricks"],
        "secondary_stone": ["blackstone", "cobblestone"],
        "accent_stone": ["gray_concrete", "deepslate_tiles"],
        "wood_trim": "dark_oak",
        "wood_accent": ["dark_oak_log", "dark_oak_fence"],
        "roof_material": "deepslate_bricks",
        "description": "Mountain fortresses with deep stone",
        "smoke":"minecraft:campfire"
    },
    
    "rocky_shores": {
        "primary_stone": ["cobblestone", "stone_bricks"],
        "secondary_stone": ["gravel", "mossy_cobblestone"],
        "accent_stone": ["cyan_terracotta", "light_blue_terracotta"],
        "wood_trim": "spruce",
        "wood_accent": ["spruce_log", "spruce_fence"],
        "roof_material": "spruce",
        "description": "Coastal settlements with rocky shores",
        "smoke":"minecraft:campfire"
    },
    
    "savanna": {
        "primary_stone": ["terracotta", "orange_terracotta"],
        "secondary_stone": ["sand", "red_terracotta"],
        "accent_stone": ["acacia_log", "yellow_terracotta"],
        "wood_trim": "acacia",
        "wood_accent": ["acacia_log", "acacia_fence"],
        "roof_material": "acacia",
        "description": "Dry savanna with terracotta and acacia",
        "smoke":"minecraft:campfire"
    },
    
    "swamp": {
        "primary_stone": ["mud", "mossy_cobblestone"],
        "secondary_stone": ["moss_block", "cobblestone"],
        "accent_stone": ["dark_oak_log", "mangrove_roots"],
        "wood_trim": "dark_oak",
        "wood_accent": ["dark_oak_log", "dark_oak_fence"],
        "roof_material": "dark_oak",
        "description": "Swamp settlements with mud and moss",
        "smoke": ["soul_campfire", "minecraft:campfire"]
    },
    
    "deep_ocean": {
        "primary_stone": ["prismarine", "dark_prismarine"],
        "secondary_stone": ["prismarine_bricks", "sea_lantern"],
        "accent_stone": ["dark_prismarine", "sea_lantern"],
        "wood_trim": "oak",
        "wood_accent": ["oak_log", "oak_fence"],
        "roof_material": "oak",
        "description": "Underwater temple aesthetic",
        "smoke": "minecraft:campfire"
    },
    
    "badlands": {
        "primary_stone": ["red_terracotta", "orange_terracotta"],
        "secondary_stone": ["yellow_terracotta", "brown_terracotta"],
        "accent_stone": ["orange_terracotta", "red_concrete"],
        "wood_trim": "acacia",
        "wood_accent": ["acacia_log", "acacia_fence"],
        "roof_material": "acacia",
        "description": "Colorful badlands with varied terracotta",
        "smoke":"minecraft:campfire"
    },
}

# Minecraft biome ID to family name mapping
BIOME_ID_MAPPING = {
    0: "deep_ocean",
    1: "plains",
    2: "desert",
    3: "mountains",
    4: "forest",
    5: "taiga",
    6: "swamp",
    10: "snowy_plains",
    12: "taiga",  # Frozen river edge
    13: "snowy_mountains",
    14: "snowy_plains",
    15: "badlands",
    16: "wooded_badlands",
    17: "badlands_plateau",
    19: "forest",  # Dense forest
    20: "jungle",
    21: "jungle_edge",
    22: "jungle_hills",
    23: "jungle_edge",
    24: "swamp",  # Mangrove swamp
    27: "rocky_shores",
    28: "rocky_shores",
    29: "savanna",
    30: "savanna_plateau",
    31: "savanna",
    35: "savanna",
    149: "jungle",
}


# DISTRICT MEMORY - prevent repetition and enforece coherence
@dataclass
class DistrictMemory:
    """Tracks materials used in district for anti-clustering"""
    district_id: int
    biome_family: str  # Which biome family this district follows
    primary_stone: str  # Locked for district coherence
    secondary_stone: str  # Locked for district coherence
    wood_trim: str  # Consistent wood per district
    roof_block: str
    roof_type: str
    history: deque = None  # Last N buildings for anti-clustering
    max_history: int = 5
    
    def __post_init__(self):
        if self.history is None:
            self.history = deque(maxlen=self.max_history)
    
    def add_building(self, stone_used: str):
        """Record material usage for anti-clustering check"""
        self.history.append(stone_used)
    
    def is_overused(self, material: str, threshold: int = 3) -> bool:
        """Check if material appeared too recently"""
        return self.history.count(material) >= threshold
    
    def get_alternatives(self, candidates: List[str]) -> List[str]:
        """Get materials not in recent history"""
        return [c for c in candidates if c not in self.history]


# intelligent palette system
class PaletteSystem:
    """Stone-first palette selection with local biome detection.
        1. Get local biome at (x, z)
        2. Lookup material family for biome
        3. Check/create district memory
        4. Select primary stone (from district or random)
        5. Select secondary stone (avoid recent)
        6. Select wood trim (consistent per biome)
        7. Return complete palette"""
    def __init__(self):
        self.district_memories: Dict[int, DistrictMemory] = {}
    
    # 1: local biome detection
    def get_local_biome(self, analysis, x: int, z: int) -> str:
        """Get biome at specific location"""
        if not analysis or not hasattr(analysis, 'best_area'):
            return "plains"  # Fallback
        
        FALLBACK_BIOME = "plains"
        try:
            li, lj = analysis.best_area.world_to_index(x, z)
            if not (0 <= li < analysis.biomes.shape[0] and 0 <= lj < analysis.biomes.shape[1]):
                return self.find_nearest_biome(analysis, li, lj)
            
            biome_id = int(analysis.biomes[li, lj])
            biome_name = BIOME_ID_MAPPING.get(biome_id)
            
            if biome_name not in MATERIAL_FAMILIES:
                logger.debug(f"Unknown biome ID {biome_id} at ({x}, {z}). Scanning nearby...")
                biome_name = self.find_nearest_biome(analysis, li, lj)
            
            return biome_name or FALLBACK_BIOME
        except Exception as e:
            logger.warning(f"Biome detection failed: {e}, using {FALLBACK_BIOME}")
            return FALLBACK_BIOME
        
    def find_nearest_biome(self, analysis, li: int, lj: int) -> str:
        if not hasattr(analysis, 'biomes'):
            return "plains"
        biome_grid = analysis.biomes
        max_li, max_lj = biome_grid.shape
        all_candidates = []

        for radius in [1, 2, 3, 5, 10]:
            for di in range(-radius, radius + 1):
                for dj in range(-radius, radius + 1):
                    ni, nj = li + di, lj + dj
                    #check bounds
                    if not (0<= ni < max_li and 0 <= nj < max_lj):
                        continue
                    #get biome at this location
                    biome_id = int(biome_grid[ni, nj])
                    biome_name = BIOME_ID_MAPPING.get(biome_id, None)
                    #only known biomes to be considered
                    if biome_name and biome_name in MATERIAL_FAMILIES:
                        distance = (di**2 + dj**2) ** 0.5  # Euclidean
                        all_candidates.append((biome_name, distance))
            #weighted selection: scan everything ->decide best
            if all_candidates:
                biome_weights = {}

                for biome_name, distance in all_candidates:
                    weight = 1 / (distance + 1)
                    biome_weights[biome_name] = biome_weights.get(biome_name, 0) + weight

                best_biome = max(biome_weights, key=biome_weights.get)

                logger.debug(
                    f"Weighted biome selection: {best_biome} from ({li}, {lj})"
                )

                return best_biome

        logger.warning(f"No known biomes found near ({li}, {lj}), using plains")
        return "plains"
    
    def get_flat_roof_variant(self, material: str) -> str:
        """Return appropriate flat block for roof"""
        special_cases = {
            "sandstone": "smooth_sandstone",
            "deepslate_bricks": "deepslate_bricks",
            "stone_bricks": "stone_bricks",
        }

        if material in special_cases:
            return special_cases[material]
        # default: wood → planks
        return f"{material}_planks"
            
    def resolve_biome_family(self, biome_name: str) -> Dict:
        """resolve biome family including parent inheritance"""
        visited = set()

        while True:
            if biome_name in visited:
                logger.warning(f"Circular biome family reference detected at {biome_name}")
                return MATERIAL_FAMILIES.get("plains", {})
            
            visited.add(biome_name)
            family = MATERIAL_FAMILIES.get(biome_name, None)
            if not family:
                logger.warning(f"Unknown biome family: {biome_name}, using plains")
                return MATERIAL_FAMILIES.get("plains", {})
            if "parent" in family:
                biome_name = family["parent"]
            else:
                return family
    
    # 2. district theme creation/retrieval
    def get_or_create_district(
        self,
        district_id: int,
        biome_family: str
    ) -> DistrictMemory:
        """Initialize or retrieve district memory.
        First building in district locks primary stone for all subsequent buildings."""
        if district_id not in self.district_memories:
            family = self.resolve_biome_family(biome_family)
            
            # Lock primary stone for district
            primary_stone = random.choice(family["primary_stone"])
            secondary_stone = random.choice(family["secondary_stone"])
            wood_trim = family["wood_trim"]
            
            memory = DistrictMemory(
                district_id=district_id,
                biome_family=biome_family,
                primary_stone=primary_stone,
                secondary_stone=secondary_stone,
                wood_trim=wood_trim,
            )
            self.district_memories[district_id] = memory
            logger.debug(
                f"District {district_id} ({biome_family}): "
                f"stone={primary_stone}, wood={wood_trim}"
            )
        
        return self.district_memories[district_id]
    
    #3. metrial selection with anti-clustering
    def select_primary_stone(
        self,
        family: Dict,
        district: DistrictMemory,
    ) -> str:
        """Select primary stone (prefers locked district stone)"""
        # Use district memory if available
        stone = district.primary_stone
        
        # Apply anti-clustering: if overused, switch to alternative
        if district.is_overused(stone, threshold=3):
            alternatives = district.get_alternatives(family["primary_stone"])
            if alternatives:

                stone = random.choice(alternatives)
                logger.debug(f"Anti-clustering: changed stone to {stone}")
        
        return stone
    
    def select_secondary_stone(
        self,
        family: Dict,
        district: DistrictMemory,
        primary_stone: str
    ) -> str:
        """Select secondary stone (different from primary)"""
        candidates = [s for s in family["secondary_stone"] if s != primary_stone]
        
        if not candidates:
            candidates = family["secondary_stone"]
        
        # Prefer stones not in recent history
        alternatives = district.get_alternatives(candidates)
        stone = random.choice(alternatives if alternatives else candidates)
        
        return stone
    
    def select_accents(
        self,
        family: Dict,
        primary_stone: str,
        wood_trim: str
    ) -> Dict[str, str]:
        """Build accent palette"""
        return {
            "accent_stone": random.choice(family["accent_stone"]),
            "wood_accent": random.choice(family["wood_accent"]),
        }
    
    def _select_floor_variant(self, biome: str, wood_trim: str) -> str:
        base = f"{wood_trim}_planks"

        if biome in ("swamp", "jungle", "forest"):
            options = [base, "moss_block"]

        elif biome in ("taiga", "snowy_plains", "snowy_mountains"):
            options = [base, "spruce_planks"]  # subtle variation

        elif biome in ("desert", "savanna", "badlands"):
            options = [base, "smooth_sandstone"]

        else:
            options = [base]

        return f"minecraft:{random.choice(options)}"
    
    def get_settlement_dominants(self, analysis) -> dict[str, str]:
        """
        Return dominant blocks for the whole settlement.
        Returns dict with keys: 'stone', 'wood', 'accent'
        """
        counts = {
            "stone": {},
            "wood": {},
            "accent": {}
        }

        # Iterate over all districts / plots
        for x in range(analysis.best_area.x_from, analysis.best_area.x_to + 1):
            for z in range(analysis.best_area.z_from, analysis.best_area.z_to + 1):
                palette = self.create_palette(x=x, z=z, district_id=0, analysis=analysis)
                for key, block in [("stone", "wall"), ("wood", "accent"), ("accent", "accent")]:
                    b = palette.get(block)
                    if b:
                        counts[key][b] = counts[key].get(b, 0) + 1

        # Pick the dominant for each type
        dominant = {}
        for key, counter in counts.items():
            if counter:
                # pick the most frequent block
                dominant[key] = max(counter.items(), key=lambda kv: kv[1])[0]
            else:
                dominant[key] = None  # fallback if nothing found

        return dominant
    
    # core: create palette
    def create_palette(
        self,
        x: int,
        z: int,
        district_id: int,
        analysis=None
    ) -> Dict[str, str]:
        """Biome → District → [Stone, Wood, Accents]
        Returns: {
            primary_stone, secondary_stone, accent_stone,
            wood_trim, wood_accent,
            roofing,
            door, window,
            forbids, special_blocks
        }"""
        
        # STEP 1: Detect local biome at this location
        biome_name = self.get_local_biome(analysis, x, z)
        biome_family = self.resolve_biome_family(biome_name)
        
        
        # STEP 2: Get or create district memory
        district = self.get_or_create_district(district_id, biome_name)
        
        # STEP 3: Select materials
        primary_stone = self.select_primary_stone(
            biome_family, district
        )
        secondary_stone = self.select_secondary_stone(biome_family, district, primary_stone)
        wood_trim = district.wood_trim
        accents = self.select_accents(biome_family, primary_stone, wood_trim)
        
        # Record usage for anti-clustering
        district.add_building(primary_stone)
        roof_material = biome_family["roof_material"]

        roof_stairs = f"minecraft:{roof_material}_stairs"
        roof_flat = f"minecraft:{self.get_flat_roof_variant(roof_material)}"
        
        # STEP 4: Build palette dictionary
        palette = {
            # CORE STRUCTURE
            "foundation": f"minecraft:{secondary_stone}",
            "wall": f"minecraft:{primary_stone}",
            "accent": f"minecraft:{accents['accent_stone']}",

            # WOOD STRUCTURE
            "beam": f"minecraft:{accents['wood_accent']}",
            "trim": f"minecraft:{wood_trim}_planks",

            # ROOF & OPENINGS
            "roof": {
                "stairs": roof_stairs,
                "flat": roof_flat
            },
            "door": f"minecraft:{wood_trim}_door",
            "window": "minecraft:glass_pane",

            # EXTRA DETAIL
            "pillar": f"minecraft:{primary_stone}",
            "floor": self._select_floor_variant(biome_name, wood_trim),
            "light": "minecraft:lantern",

            # METADATA
            "biome": biome_name,
            "district_id": district_id,
        }
        
        logger.info(
            f"Palette: {primary_stone} + {secondary_stone} + {wood_trim} "
            f"({biome_name})"
        )
        
        return palette
