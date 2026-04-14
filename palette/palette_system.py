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
    
# DISTRICT MEMORY - prevent repetition and enforece coherence
class DistrictMemory:
    """Tracks materials used in district for anti-clustering"""
    def __init__(self, district_id: int, history_length: int = 2):
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
            "stone_bricks": {"stripped_oak_log": 0.95, "oak_log": 0.93, "dark_oak_log": 0.90, "spruce_log": 0.70},
            "sandstone": {"acacia_log": 0.95, "stripped_acacia_log": 0.93, "oak_log": 0.70},
            "mossy_stone_bricks": {"jungle_log": 0.95, "mangrove_log": 0.92, "oak_log": 0.85},
            "deepslate_bricks": {"spruce_log": 0.95, "stripped_spruce_log": 0.93},
            "red_sandstone": {"dark_oak_log": 0.95, "stripped_dark_oak_log": 0.93},
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
                biome_hint = str(analysis.biomes[li, lj]).lower()
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
            palettes[idx] = palette
            
        return palettes

    # Weighted choice utility
    def _get_weighted_variant(self, variant_data: Any) -> str:
        """Pick a material based on weights"""
        if isinstance(variant_data, dict) and "variants" in variant_data:
            return random.choices(variant_data["variants"], weights=variant_data.get("weights"), k=1)[0]
        # List: ["stone", "cobblestone", "andesite"]
        if isinstance(variant_data, list):
            return random.choice(variant_data)
        #Raw String: "oak_planks"
        return str(variant_data)
            
    def _resolve_archetype(self, biome_name: str = "") -> str:
        """resolve raw biome name to archetype using a Priority-Ordered Keyword strategy to handle vanilla & modded biomes."""
        # remove namespace and case sensitivity
        name = biome_name.lower().replace("minecraft:", "")

        # 2. Specific Biome Overrides
        if "cherry" in name: return "CHERRY_GROVE"
        if "savanna" in name: return "SAVANNA"
        if any(w in name for w in ["badlands", "mesa", "terracotta", "red_sand"]): 
            return "BADLANDS"
        # 3. Other Climates
        if any(w in name for w in ["jungle", "swamp", "mangrove", "bamboo", "moss", "lush", "mud", "vine", "podzol"]): 
            return "LUSH"
        if any(w in name for w in ["ice", "snow", "frozen", "taiga", "powder"]): 
            return "FROZEN"
        if any(w in name for w in ["desert", "sand", "dunes", "cactus"]): 
            return "ARID"
        if any(w in name for w in ["ocean", "river", "beach", "water", "prismarine"]):
            return "AQUATIC"
        return "TEMPERATE"
    
    # 2. district theme creation/retrieval
    def _get_or_create_district(self, district_id: int) -> DistrictMemory:
        if district_id not in self.district_memories:
            self.district_memories[district_id] = DistrictMemory(district_id)
        return self.district_memories[district_id]
    
    # core: create palette
    def create_palette(self, district_id: int,
                       biome_name: str = "", district_type: str = "residential") -> dict:
        archetype = self._resolve_archetype(biome_name)
        lib = self.MATERIAL_LIBRARY.get(archetype, self.MATERIAL_LIBRARY["TEMPERATE"])
        district_memory = self._get_or_create_district(district_id)

        # Weighted primary wall selection with anti-clustering
        primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
        # Anti-clustering: re-roll if same as last few
        for _ in range(5):
            if not district_memory.is_overused(primary_wall): break
            primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
        district_memory.add_building(primary_wall)

        #roof selection with anti-clustering
        roof_options = lib["structure"]["roof"]
        roof_set = self._get_weighted_variant(roof_options)
        roof_label = roof_set['label'] if isinstance(roof_set, dict) else str(roof_set)
        for i in range(6):
            # Check the label to see if we've used this wood/stone type recently
            if not district_memory.is_overused(roof_set.get('label', 'default')): 
                break
            
            # If we are failing to find variety, force a random uniform choice
            if i > 5 and isinstance(roof_options, dict) and "variants" in roof_options:
                roof_set = random.choice(roof_options["variants"])
            else:
                roof_set = self._get_weighted_variant(roof_options)
        
        district_memory.add_building(roof_label)

        accent_raw = lib["structure"]["accent"]
        accent = self._pick_compatible_material(primary_wall, accent_raw)
        is_wood = any(x in accent for x in ["log", "stem", "wood", "hyphae"])
        accent_beam = f"minecraft:stripped_{accent}" if is_wood and "stripped" not in accent else f"minecraft:{accent}"
        # Compose base palette
        palette = {
            "archetype": archetype,
            "role:core": [
                f"minecraft:{primary_wall}",
                f"minecraft:{lib['structure']['foundation']}",
                f"minecraft:{roof_set['label']}",
            ],
            "role:accent": [
                f"minecraft:{accent}",
                accent_beam,
            ],
            "role:utility": [
                "minecraft:oak_door",
                "minecraft:oak_fence",
                f"minecraft:{roof_set['slab']}",
            ],
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

        palette["road_config"] = {
            "main": self.get_road_material(biome_name, is_main=True),
            "path": self.get_road_material(biome_name, is_main=False),
            "edge": self.get_road_component(biome_name, is_main=False, component_type="edge")
        }

        return palette
    
    def _pick_compatible_material(self, primary_wall: str, accent_options) -> str:
        """Pick accent material based on affinity with wall."""
        accent_list = accent_options if isinstance(accent_options, list) else [accent_options]
        
        # Get affinity scores for this wall
        affinity = self.MATERIAL_AFFINITY.get(primary_wall, {})
        default_affinity = self.MATERIAL_AFFINITY.get("_default", 0.6)
        
        # Score each accent option
        scored = [(a, affinity.get(a, default_affinity)) for a in accent_list]
        accents, scores = zip(*scored)
        return random.choices(accents, weights=scores, k=1)[0]
    
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
        clean_base = base_block.replace("_planks", "").replace("planks", "").replace("bricks", "brick")
        if clean_base.endswith("s") and not clean_base.endswith("ss"): clean_base = clean_base[:-1]

        suffix = "_stairs" if component_type == "stair" else "_slab"
        key = f"{clean_base}{suffix}"
        return f"minecraft:{key}" if self._block_exists(key, base_block) else f"minecraft:oak{suffix}"
    
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

def test_archetype_resolution():
    ps = PaletteSystem()
    
    # Test cases representing what analysis.surface_blocks might return
    test_scenarios = [
        ("Sand in Desert", "minecraft:sand", "ARID"),
        ("Sand on Beach", "minecraft:beach", "AQUATIC"),
        ("Snow in Taiga", "minecraft:snow_block", "FROZEN"),
        ("Mud in Swamp", "minecraft:mud", "LUSH"),
        ("Jungle Log", "minecraft:jungle_log", "LUSH"),
        ("The Problem Case", "minecraft:grass_block", "LUSH"), # This usually fails
    ]

    print(f"{'INPUT BLOCK':<25} | {'EXPECTED':<12} | {'RESULT':<12} | {'STATUS'}")
    print("-" * 70)

    for description, block, expected in test_scenarios:
        actual = ps._resolve_archetype(block)
        status = "✅ PASS" if actual == expected else "❌ FAIL (Got " + actual + ")"
        print(f"{block:<25} | {expected:<12} | {actual:<12} | {status}")

if __name__ == "__main__":
    test_archetype_resolution()