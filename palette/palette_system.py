from __future__ import annotations
import random
from typing import Any, Dict, List
from collections import deque
from enum import Enum
from palette.material_library import MATERIAL_LIBRARY
import logging

logger = logging.getLogger(__name__)
"""
paletteSystem returns materials for buildings and roads based on biome archetype, district theme.
Handle weighted variennts and anti-clustering district.
Roads are returned per-archetyper and main/path distinction.
"""

class MaterialRole(Enum):
    """Categories of materials in buildings."""
    CORE = "structural"      # Walls, floors, foundation
    ACCENT = "decorative"    # Logs, trim, highlights
    UTILITY = "functional"   # Doors, windows, fences
    LIGHT = "atmospheric"    # Lanterns, glowstone

class StructurePersonality(Enum):
    """Building complexity and material distribution."""
    SIMPLE = {"core": 0.80, "accent": 0.10, "utility": 0.10, "light": 0.00}
    STANDARD = {"core": 0.60, "accent": 0.20, "utility": 0.15, "light": 0.05}
    DECORATED = {"core": 0.50, "accent": 0.30, "utility": 0.15, "light": 0.05}
    ORNATE = {"core": 0.40, "accent": 0.40, "utility": 0.15, "light": 0.05}
    
# DISTRICT MEMORY - prevent repetition and enforece coherence
class DistrictMemory:
    """Tracks materials used in district for anti-clustering"""
    def __init__(self, district_id: int, history_length: int = 5):
        self.district_id = district_id
        self.history = deque(maxlen=history_length)

    def add_building(self, material: str):
        """Record material usage for anti-clustering check"""
        self.history.append(material)
    
    def is_overused(self, material: str) -> bool:
        """Check if material appeared too recently"""
        return material in self.history

# intelligent palette system
class PaletteSystem:
    """Environment-aware, archetype-driven palette system + road."""
    def __init__(self):
        self.district_memories: Dict[int, DistrictMemory] = {}
        self.MATERIAL_LIBRARY = MATERIAL_LIBRARY
        self.MATERIAL_AFFINITY = self._build_affinity_graph()

    def _build_affinity_graph(self) -> Dict[str, Dict[str, float]]:
        """
        Build a compatibility graph between materials.
        Higher score = better together (0-1 scale)
        """
        return {
            # Stone materials are compatible with warm wood
            "stone_bricks": {
                "stripped_oak_log": 0.95,
                "oak_log": 0.93,
                "dark_oak_log": 0.90,
                "spruce_log": 0.70,
                "jungle_log": 0.65,
                "prismarine_bricks": 0.30,
            },
            
            # Sandstone pairs with acacia
            "sandstone": {
                "acacia_log": 0.95,
                "stripped_acacia_log": 0.93,
                "oak_log": 0.70,
            },
            
            # Mossy stone with jungle materials
            "mossy_stone_bricks": {
                "jungle_log": 0.95,
                "mangrove_log": 0.92,
                "oak_log": 0.85,
            },
            
            # Prismarine with oak/spruce
            "prismarine_bricks": {
                "oak_log": 0.90,
                "spruce_log": 0.88,
            },
            
            # Deepslate with spruce
            "deepslate_bricks": {
                "spruce_log": 0.95,
                "stripped_spruce_log": 0.93,
            },
            
            # Red sandstone with dark oak
            "red_sandstone": {
                "dark_oak_log": 0.95,
                "stripped_dark_oak_log": 0.93,
            },
            
            # Default: assume medium compatibility
            "_default": 0.60,
        }

    def generate(self, analysis, districts) -> Dict[int, Any]:
        """
        Modified to accept WorldAnalysisResult.
        Generates a BiomePalette for every district in one pass.
        """
        palettes: Dict[int, Any] = {}
        area = analysis.best_area
        for idx, dtype in districts.types.items():
            district = districts.district_list[idx]
            wx, wz = int(district.center_x), int(district.center_z)

            # Sample the biome/surface from the analysis array
            try:
                # Convert world coordinates to local array indices
                li, lj = area.world_to_index(wx, wz)
                # Use surface_blocks as the primary hint for _resolve_archetype
                biome_hint = str(analysis.surface_blocks[li, lj])
            except (ValueError, IndexError):
                biome_hint = "plains"
                logger.warning(
                    "  District %d (%s): centre (%d, %d) outside analysis area — defaulting biome hint to 'plains'.",
                    idx, dtype, wx, wz,
                )

            # Create the building palette
            palette = self.create_palette(
                district_id=idx,
                biome_name=biome_hint,
                district_type=dtype
            )
            logger.info(
                "  District %d (%s): surface=%r → archetype=%s  wall=%s  roof=%s",
                idx, dtype, biome_hint, palette["archetype"],
                palette.get("wall"), palette.get("roof_block"),
            )

            # Inject road materials into the same palette object for the builders
            palette["path"] = self.get_road_material(biome_hint, is_main=False)
            palette["path_edge"] = self.get_road_component(biome_hint, is_main=False, component_type="edge")
            palette["path_slab"] = self.get_road_component(biome_hint, is_main=False, component_type="slab")
            
            palettes[idx] = palette
            
        return palettes

    # Weighted choice utility
    def _get_weighted_variant(self, variant_data: Any) -> str:
        """Pick a material based on weights"""
        if isinstance(variant_data, dict):
            if "variants" in variant_data:
                return random.choices(
                    variant_data["variants"], 
                    weights=variant_data.get("weights"), 
                    k=1
                )[0]
            return variant_data
        # List: ["stone", "cobblestone", "andesite"]
        if isinstance(variant_data, list):
            return random.choice(variant_data)
        #Raw String: "oak_planks"
        return str(variant_data)
            
    def _resolve_archetype(self, biome_name: str = "") -> str:
        """resolve raw biome name to archetype using a Priority-Ordered Keyword strategy to handle vanilla & modded biomes."""
        # remove namespace and case sensitivity
        name = biome_name.lower().replace("minecraft:", "")

        # 1 priority layer: Specific Biomes (The "Special Look" overrides)
        if "savanna" in name: return "SAVANNA"  # Acacia/Orange wood focus
        if "badlands" in name or "mesa" in name: return "BADLANDS" # Terracotta/Red Sandstone focus
        if "cherry" in name: return "CHERRY_GROVE" # Pink/Oriental aesthetic

        # 2. environmental layer: Climate Grouping
        # FROZEN: If it sounds cold, it gets the winter palette
        if any(word in name for word in ["ice", "snow", "frozen", "taiga", "slopes", "jagged"]): return "FROZEN"
        # ARID: High heat, low moisture (primarily Deserts)
        if any(word in name for word in ["desert", "dunes"]): return "ARID"
        # LUSH: High moisture, dense vegetation
        if any(word in name for word in ["jungle", "swamp", "mangrove", "bamboo"]): return "LUSH"
        # AQUATIC: Near or in water (influences foundation/materials)
        if any(word in name for word in ["ocean", "river", "beach", "coast"]): return "AQUATIC"
        
        # 3. default: The "Medieval/Standard" fallback
        return "TEMPERATE"    #Plains, Forest, Meadow, Birch Forest...
    
    # 2. district theme creation/retrieval
    def _get_or_create_district(self, district_id: int) -> DistrictMemory:
        if district_id not in self.district_memories:
            self.district_memories[district_id] = DistrictMemory(district_id)
        return self.district_memories[district_id]
    
    # core: create palette
    def create_palette(self, district_id: int,
                       biome_name: str = "", district_type: str = "residential") -> dict:
        archetype = self._resolve_archetype(biome_name)
        lib = MATERIAL_LIBRARY[archetype]
        district_memory = self._get_or_create_district(district_id)

        # Weighted primary wall selection with anti-clustering
        primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
        roof_set = self._get_weighted_variant(lib["structure"]["roof"])
        # Anti-clustering: re-roll if same as last few
        attempts = 0
        while district_memory.is_overused(primary_wall) and attempts < 3:
            primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
            roof_set = self._get_weighted_variant(lib["structure"]["roof"])
            attempts += 1
        district_memory.add_building(primary_wall)
        district_memory.add_building(roof_set)

        accent_raw = lib["structure"]["accent"]
        accent = self._pick_compatible_material(primary_wall, accent_raw)
        is_wood = any(x in accent for x in ["log", "stem", "wood", "hyphae"])
        accent_beam = f"minecraft:stripped_{accent}" if is_wood and "stripped" not in accent else f"minecraft:{accent}"
        # Compose base palette
        palette = {
            "archetype": archetype,
            
            # Role: CORE (structural)
            "role:core": [
                f"minecraft:{primary_wall}",
                f"minecraft:{lib['structure']['foundation']}",
                f"minecraft:{roof_set['label']}",
            ],
            
            # Role: ACCENT (decorative)
            "role:accent": [
                f"minecraft:{accent}",
                accent_beam,
            ],
            
            # Role: UTILITY (functional)
            "role:utility": [
                "minecraft:oak_door",
                "minecraft:oak_fence",
                f"minecraft:{roof_set['slab']}",
            ],
            
            # Role: LIGHT (atmospheric)
            "role:light": [
                "minecraft:lantern",
                "minecraft:soul_lantern" if archetype == "FROZEN" else "minecraft:lantern",
            ],
            
            # Flat structure for backward compatibility
            "wall": f"minecraft:{primary_wall}",
            "foundation": f"minecraft:{lib['structure']['foundation']}",
            "accent": f"minecraft:{accent}",
            "roof_block": f"minecraft:{roof_set['block']}",
            "roof_stairs": f"minecraft:{roof_set['stairs']}",
            "roof_slab": f"minecraft:{roof_set['slab']}",
            "accent_beam": accent_beam,
        }

        # Add decor with safe list handling
        for key, value in lib["structure"]["decor"].items():
            if isinstance(value, list):
                palette[key] = f"minecraft:{random.choice(value)}"
            else:
                palette[key] = f"minecraft:{value}"
        
        if "door" not in palette:
            palette["door"] = "minecraft:oak_door"
            logger.debug("  [palette] 'door' not in decor — defaulting to oak_door")
        if "fence" not in palette:
            palette["fence"] = "minecraft:oak_fence"
            logger.debug("  [palette] 'fence' not in decor — defaulting to oak_fence")
        if "floor" not in palette:
            floor_val = f"minecraft:{primary_wall}" if "_planks" in primary_wall else "minecraft:oak_planks"
            palette["floor"] = floor_val
            logger.debug("  [palette] 'floor' not in decor — defaulting to %s", floor_val)
        if "interior_light" not in palette:
            palette["interior_light"] = "minecraft:pearlescent_froglight"
            logger.debug("  [palette] 'interior_light' not in decor — defaulting to pearlescent_froglight")

        # Merge district-specific overrides
        district_data = lib["districts"].get(district_type, {})
        for k, v in district_data.items():
            if isinstance(v, list):
                palette[k] = f"minecraft:{random.choice(v)}"
            else:
                palette[k] = f"minecraft:{v}"

        return palette
    
    def _pick_compatible_material(self, primary_wall: str, accent_options) -> str:
        """Pick accent material based on affinity with wall."""
        accent_list = accent_options if isinstance(accent_options, list) else [accent_options]
        
        # Get affinity scores for this wall
        affinity = self.MATERIAL_AFFINITY.get(primary_wall, {})
        default_affinity = self.MATERIAL_AFFINITY.get("_default", 0.6)
        
        # Score each accent option
        scored_options = []
        for accent in accent_list:
            score = affinity.get(accent, default_affinity)
            scored_options.append((accent, score))
        
        # Pick weighted by score
        accents, scores = zip(*scored_options)
        selected = random.choices(accents, weights=scores, k=1)[0]
        
        logger.debug(f"[affinity] wall={primary_wall} → accent={selected} (score={affinity.get(selected, default_affinity)})")
        
        return selected
    
    # get materials by role for buildings
    def get_materials_by_role(self, palette: dict, role: MaterialRole) -> List[str]:
        """
        Get all materials for a specific role.
        
        Usage:
            core_materials = palette_system.get_materials_by_role(palette, MaterialRole.CORE)
            random_core = random.choice(core_materials)
        """
        key = f"role:{role.name.lower()}"
        return palette.get(key, [palette.get("wall", "minecraft:stone")])
    
    #4 road components :stairs/slabs; main/path
    def get_road_component(self, biome_name: str, is_main: bool, component_type: str = "base", existing_block: str = None) -> str:
        """Returns a road block for biome archetype (base, stair, slab, edge)."""
        archetype = self._resolve_archetype(biome_name)
        archetype_data = self.MATERIAL_LIBRARY.get(archetype, self.MATERIAL_LIBRARY["TEMPERATE"])
        road_cfg = archetype_data.get("roads", self.MATERIAL_LIBRARY["TEMPERATE"]["roads"])

        #existing block to avoid double randomisation
        if existing_block:
            base_block = existing_block.replace("minecraft:", "")
        else:
            variant_data = road_cfg["main" if is_main else "path"]
            base_block = self._get_weighted_variant(variant_data) if isinstance(variant_data, dict) else variant_data

        if component_type == "edge": return f"minecraft:{road_cfg.get('edge', 'cobblestone_slab')}"
        if component_type == "base": return f"minecraft:{base_block}"
        
        # base block -deal with block name conversion issues (3)
        clean_base = base_block
        if "planks" in base_block:
            clean_base = base_block.replace("_planks", "").replace("planks", "")
        elif "bricks" in base_block:
            clean_base = base_block.replace("bricks", "brick")
        elif base_block == "bricks":
            clean_base = "brick"
        elif base_block.endswith("s") and not base_block.endswith("ss"):
            clean_base = base_block[:-1]

        # stairs
        if component_type == "stair":
            stair_key = f"{clean_base}_stairs"
            return f"minecraft:{stair_key}" if self._block_exists(stair_key, base_block) else "minecraft:oak_stairs"

        # slabs
        if component_type == "slab":
            slab_key = f"{clean_base}_slab"
            return f"minecraft:{slab_key}" if self._block_exists(slab_key, base_block) else "minecraft:oak_slab"

        raise ValueError(f"Unknown road component: {component_type}")
    
    def get_road_material(self, biome_name: str, is_main: bool = True) -> str:
        return self.get_road_component(biome_name, is_main, component_type="base")
    
    #check block existence
    def _block_exists(self, key: str, base: str) -> bool:
        invalid_exact = {"dirt_path", "gravel", "grass_block", "coarse_dirt", "mud", "moss_block", "smooth_stone", "stone","terracotta"}
        if base in invalid_exact:
            return False
        # block containing keyword lacks variants: 'white_wool', 'blue_concrete', 'glass_pane'...
        invalid_categories = ["wool", "glass", "concrete", "powder", "ice", "leaves"]
        if any(category in base for category in invalid_categories):
            return False

        # fallback: Sandstone, Bricks, Tiles, Planks
        return True
    
def palette_get(palette: dict, key: str,default: str = "minecraft:stone") -> str:
    """Safe get for palette with default fallback."""
    return palette.get(key, default)
    
# if __name__ == "__main__":
#     # Initialize the system
#     ps = PaletteSystem()
#     # No need to assign MATERIAL_LIBRARY, it's already imported
    
#     print("--- REAL-DATA PALETTE VALIDATION ---")

#     # 1. Test Wood-Stripping for all Archetypes
#     # -------------------------------------------------------------------------
#     print("\n[Test 1] Wood Stripping & Accent Beams")
#     test_cases = [
#         ("minecraft:plains", "TEMPERATE"), 
#         ("minecraft:frozen_ocean", "FROZEN"),
#         ("minecraft:jungle", "LUSH"),
#         ("minecraft:savanna", "SAVANNA")
#     ]

#     for biome, arch in test_cases:
#         pal = ps.create_palette(district_id=101, biome_name=biome)
#         accent = pal["accent"]
#         beam = pal["accent_beam"]
        
#         # Verify result
#         print(f"Archetype {arch:9} | Accent: {accent:20} | Beam: {beam}")
        
#         if any(w in accent for w in ["log", "stem", "wood", "hyphae"]):
#             if "stripped" not in accent:
#                 assert "stripped" in beam, f"Error: {accent} should have a stripped beam!"
    
#     # 2. Test Road Component Formatting (The "Plural" Logic)
#     # -------------------------------------------------------------------------
#     print("\n[Test 2] Road Component Conversions")
#     # Testing specific tricky strings from your library
#     road_formatting_tests = [
#         ("TEMPERATE", "stone_bricks", "stone_brick_slab"), # bricks -> brick
#         ("AQUATIC", "oak_planks", "oak_slab"),            # planks -> slab
#         ("FROZEN", "deepslate_bricks", "deepslate_brick_slab"),
#         ("ARID", "smooth_sandstone", "smooth_sandstone_slab")
#     ]

#     for arch, base, expected_slab in road_formatting_tests:
#         # Using existing_block to test the string transformation logic specifically
#         res = ps.get_road_component(arch.lower(), is_main=True, component_type="slab", existing_block=base)
#         print(f"Base: {base:20} -> Slab: {res}")
#         assert res == f"minecraft:{expected_slab}", f"Formatting Error: Expected {expected_slab}, got {res}"

#     # 3. Test Anti-Clustering (District Diversity)
#     # -------------------------------------------------------------------------
#     print("\n[Test 3] District Variety (Anti-Clustering)")
#     walls_used = []
#     # Generate 5 buildings in the same district
#     for _ in range(5):
#         pal = ps.create_palette(district_id=5, biome_name="minecraft:plains")
#         walls_used.append(pal["wall"])
    
#     unique_walls = set(walls_used)
#     print(f"Walls chosen in District 5: {walls_used}")
#     if len(ps.MATERIAL_LIBRARY["TEMPERATE"]["structure"]["primary_wall"]["variants"]) > 1:
#         assert len(unique_walls) > 1, "Variety Error: District Memory is not cycling materials!"

#     print("\n--- ALL REAL-DATA TESTS PASSED ---")

def test_roof_diversity():
    # Initialize your system (assumes class name is PaletteSystem)
    ps = PaletteSystem()
    
    test_district_id = 101
    biome = "minecraft:forest"
    house_count = 10
    
    print(f"--- Testing Roof Diversity for {house_count} Houses ---")
    print(f"Biome: {biome} | District: {test_district_id}\n")
    
    results = []
    
    for i in range(1, house_count + 1):
        # This MUST be called inside the loop to trigger a new random choice
        pal = ps.create_palette(district_id=test_district_id, biome_name=biome)
        
        wall = pal.get("wall", "N/A").replace("minecraft:", "")
        roof = pal.get("roof_block", "N/A").replace("minecraft:", "")
        
        results.append(roof)
        print(f"House {i:02d}: Wall [{wall:15}] | Roof Set: [{roof}]")

    # Statistical Summary
    unique_roofs = set(results)
    print(f"\n--- Analysis ---")
    print(f"Unique Roof Types Found: {len(unique_roofs)}")
    for r_type in unique_roofs:
        count = results.count(r_type)
        print(f"- {r_type}: {count} houses ({(count/house_count)*100:.0f}%)")

    if len(unique_roofs) > 1:
        print("\n✅ PASS: Roof diversity is functioning.")
    else:
        print("\n❌ FAIL: Only one roof type detected. Check if selection logic is inside the loop.")

# Run the test
if __name__ == "__main__":
    test_roof_diversity()