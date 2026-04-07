from __future__ import annotations
import random
from typing import Any, Dict, TypedDict
from collections import deque
from palette.material_library import MATERIAL_LIBRARY
import logging

logger = logging.getLogger(__name__)
"""
paletteSystem returns materials for buildings and roads based on biome archetype, district theme.
Handle weighted variennts and anti-clustering district.
Roads are returned per-archetyper and main/path distinction.
"""

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
    banner:         str
    roof_block:     str
    path_edge:      str
    path_slab:      str

# DISTRICT MEMORY - prevent repetition and enforece coherence
class DistrictMemory:
    """Tracks materials used in district for anti-clustering"""
    def __init__(self, district_id: int, history_length: int = 3):
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

            # Create the building palette
            palette = self.create_palette(
                district_id=idx, 
                biome_name=biome_hint, 
                district_type=dtype
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
            return random.choices(
                variant_data["variants"], 
                weights=variant_data.get("weights"), 
                k=1
            )[0]
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
        # logger.info(f"Resolved {biome_name} to {archetype} style.")
        lib = MATERIAL_LIBRARY[archetype]
        district_memory = self._get_or_create_district(district_id)

        # Weighted primary wall selection with anti-clustering
        primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
        # Anti-clustering: re-roll if same as last few
        attempts = 0
        while district_memory.is_overused(primary_wall) and attempts < 5:
            primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
            attempts += 1
        district_memory.add_building(primary_wall)

        accent_raw = lib["structure"]["accent"]
        accent = self._get_weighted_variant(accent_raw)

        # Compose base palette
        palette = {
            "archetype": archetype,
            "wall": f"minecraft:{primary_wall}",
            "foundation": f"minecraft:{lib['structure']['foundation']}",
            "accent": f"minecraft:{accent}",
            "roof_block": f"minecraft:{lib['structure']['roof']['block']}",
            "roof_stairs": f"minecraft:{lib['structure']['roof']['stairs']}",
            "roof_slab": f"minecraft:{lib['structure']['roof']['slab']}",
            "accent_beam": f"minecraft:stripped_{accent}_log" if ("log" in accent and "_log" not in accent) else f"minecraft:{accent}_log" if "log" not in accent else f"minecraft:{accent}",
        }

        # Add decor with safe list handling
        for key, value in lib["structure"]["decor"].items():
            if isinstance(value, list):
                palette[key] = f"minecraft:{random.choice(value)}"
            else:
                palette[key] = f"minecraft:{value}"
        
        if "door" not in palette:
            palette["door"] = "minecraft:oak_door"
        if "fence" not in palette:
            palette["fence"] = "minecraft:oak_fence"
        if "floor" not in palette:
            palette["floor"] = f"minecraft:{primary_wall}" if "_planks" in primary_wall else "minecraft:oak_planks"
        if "interior_light" not in palette:
            palette["interior_light"] = "minecraft:pearlescent_froglight"

        # Merge district-specific overrides
        district_data = lib["districts"].get(district_type, {})
        for k, v in district_data.items():
            if isinstance(v, list):
                palette[k] = f"minecraft:{random.choice(v)}"
            else:
                palette[k] = f"minecraft:{v}"

        return palette
    
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
    

# TESTING
# if __name__ == "__main__":
#     ps = PaletteSystem()
 
#     print("=== TEST 1: Biome Archetype Resolution ===")
#     test_biomes = [
#         "minecraft:plains", "minecraft:savanna", "minecraft:badlands",
#         "minecraft:cherry_grove", "minecraft:snowy_tundra",
#         "minecraft:desert", "minecraft:jungle", "minecraft:river"
#     ]
#     for biome in test_biomes:
#         archetype = ps._resolve_archetype(biome)
#         print(f"{biome} -> {archetype}")
 
#     print("\n=== TEST 2: Palette Creation (Anti-clustering & district memory) ===")
#     district_id = 1
#     for i in range(5):
#         palette = ps.create_palette(temp=0.7, downfall=0.5, district_id=district_id, biome_name="plains")
#         print(f"Building {i+1} [{palette['archetype']}]: Wall={palette['wall']}, Accent={palette['accent']}")
#         # ✅ NEW: Verify all required keys exist
#         required_keys = ["wall", "foundation", "accent", "accent_beam", "roof", "roof_block", "roof_stairs", "roof_slab", "door", "fence", "floor", "interior_light"]
#         missing = [k for k in required_keys if k not in palette]
#         if missing:
#             print(f"  ⚠️  Missing keys: {missing}")
#         else:
#             print(f"  ✅ All required keys present")
 
#     print("\n=== TEST 3: Road Component Generation ===")
#     road_biomes = ["plains", "desert", "savanna", "jungle", "snowy_tundra"]
#     for biome in road_biomes:
#         base = ps.get_road_component(biome, is_main=True, component_type="base")
#         stair = ps.get_road_component(biome, is_main=True, component_type="stair", existing_block=base)
#         slab = ps.get_road_component(biome, is_main=True, component_type="slab", existing_block=base)
#         print(f"{biome}: Base={base}, Stair={stair}, Slab={slab}")
 
#     print("\n=== TEST 4: get_road_material Shortcut ===")
#     for biome in ["plains", "desert", "jungle"]:
#         mat = ps.get_road_material(biome, is_main=False)
#         print(f"{biome} path material -> {mat}")
 
#     print("\n=== TEST 5: Block Existence Checks ===")
#     test_blocks = [
#         "dirt_path", "gravel", "grass_block", "coarse_dirt", "mud", "moss_block", 
#         "smooth_stone", "stone", "terracotta", "oak_planks", "stone_bricks", 
#         "white_wool", "blue_concrete", "glass_pane", "sandstone", "polished_andesite"
#     ]
#     for block in test_blocks:
#         exists = ps._block_exists(block, block)
#         print(f"{block}: Can have stairs/slabs? {exists}")
 
#     print("\n=== TEST 6: palette_get() function ===")
#     p = ps.create_palette(0.7, 0.5, 1, "plains", "residential")
#     print(f"Existing key 'wall': {ps.palette_get(p, 'wall')}")
#     print(f"Missing key 'custom': {ps.palette_get(p, 'custom', 'minecraft:fallback_block')}")