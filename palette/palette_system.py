from __future__ import annotations
import random
from typing import Any, Dict
from collections import deque
from palette.material_library import MATERIAL_LIBRARY
import logging

logger = logging.getLogger(__name__)

"""
PaletteSystem returns materials for buildings and roads based on biome archetype and district theme.
Handles weighted variants and anti-clustering per district.
Roads are returned per-archetype with main/path distinction.

FIXES:
- accent_beam construction was broken: could produce "stripped_stripped_oak_log" or
  other malformed names. Now simply stores the accent as-is and adds a separate
  accent_beam key that is always the stripped variant when the accent is a log,
  falling back to the accent itself otherwise.
- get_road_component name-mangling used a catch-all endswith("s") strip that
  corrupted names like "packed_ice" -> "packed_ic". Replaced with an explicit
  lookup table for known plural->singular mappings.
- palette["path_slab"] was re-randomising the base block independently of
  palette["path"], so the slab could mismatch the path surface. Now passes
  existing_block so both are derived from the same chosen block.
"""


# ── District Memory ──────────────────────────────────────────────────────────

class DistrictMemory:
    """Tracks materials used in a district for anti-clustering."""

    def __init__(self, district_id: int, history_length: int = 3):
        self.district_id = district_id
        self.history: deque[str] = deque(maxlen=history_length)

    def add_building(self, material: str) -> None:
        self.history.append(material)

    def is_overused(self, material: str) -> bool:
        return material in self.history


# ── Palette System ───────────────────────────────────────────────────────────

class PaletteSystem:
    """Environment-aware, archetype-driven palette system + road."""

    def __init__(self):
        self.district_memories: Dict[int, DistrictMemory] = {}
        self.MATERIAL_LIBRARY = MATERIAL_LIBRARY

    # ── Public entry point ──────────────────────────────────────────────────

    def generate(self, analysis, districts) -> Dict[int, Any]:
        """
        Generates a BiomePalette for every district in one pass.
        Accepts a WorldAnalysisResult and a Districts object.
        """
        palettes: Dict[int, Any] = {}
        area = analysis.best_area

        for idx, dtype in districts.types.items():
            district = districts.district_list[idx]
            wx, wz = int(district.center_x), int(district.center_z)

            try:
                li, lj = area.world_to_index(wx, wz)
                biome_hint = str(analysis.surface_blocks[li, lj])
            except (ValueError, IndexError):
                biome_hint = "plains"
                logger.warning(
                    "  District %d (%s): centre (%d, %d) outside analysis area "
                    "— defaulting biome hint to 'plains'.",
                    idx, dtype, wx, wz,
                )

            palette = self.create_palette(
                district_id=idx,
                biome_name=biome_hint,
                district_type=dtype,
            )
            logger.info(
                "  District %d (%s): surface=%r → archetype=%s  wall=%s  roof=%s",
                idx, dtype, biome_hint,
                palette["archetype"], palette.get("wall"), palette.get("roof_block"),
            )

            # Road materials — derive path_slab from the same block as path
            # FIX: set path first, then derive path_base_block from it so slab matches
            palette["path"]       = self.get_road_material(biome_hint, is_main=False)
            path_base_block = palette["path"].replace("minecraft:", "")
            palette["path_edge"]  = self.get_road_component(biome_hint, is_main=False, component_type="edge")
            palette["path_slab"]  = self.get_road_component(
                biome_hint, is_main=False, component_type="slab",
                existing_block=path_base_block,
            )

            palettes[idx] = palette

        return palettes

    # ── Internal helpers ────────────────────────────────────────────────────

    def _get_weighted_variant(self, variant_data: Any) -> str:
        """Pick a material respecting optional weights."""
        if isinstance(variant_data, dict):
            return random.choices(
                variant_data["variants"],
                weights=variant_data.get("weights"),
                k=1,
            )[0]
        if isinstance(variant_data, list):
            return random.choice(variant_data)
        return str(variant_data)

    def _resolve_archetype(self, biome_name: str = "") -> str:
        """
        Resolve a raw biome name (possibly namespaced) to a library archetype
        using priority-ordered keyword matching.
        """
        name = biome_name.lower().replace("minecraft:", "")

        # 1. Specific biomes (highest priority overrides)
        if "savanna"                       in name: return "SAVANNA"
        if "badlands" in name or "mesa"    in name: return "BADLANDS"
        if "cherry"                        in name: return "CHERRY_GROVE"

        # 2. Climate groupings
        if any(w in name for w in ["ice", "snow", "frozen", "taiga", "slopes", "jagged"]):
            return "FROZEN"
        if any(w in name for w in ["desert", "dunes"]):
            return "ARID"
        if any(w in name for w in ["jungle", "swamp", "mangrove", "bamboo"]):
            return "LUSH"
        if any(w in name for w in ["ocean", "river", "beach", "coast"]):
            return "AQUATIC"

        # 3. Default fallback
        return "TEMPERATE"

    def _get_or_create_district(self, district_id: int) -> DistrictMemory:
        if district_id not in self.district_memories:
            self.district_memories[district_id] = DistrictMemory(district_id)
        return self.district_memories[district_id]

    # ── Core palette builder ────────────────────────────────────────────────

    def create_palette(
        self,
        district_id: int,
        biome_name: str = "",
        district_type: str = "residential",
    ) -> dict:
        archetype = self._resolve_archetype(biome_name)
        lib = MATERIAL_LIBRARY[archetype]
        district_memory = self._get_or_create_district(district_id)

        # Weighted primary wall with anti-clustering re-roll
        primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
        attempts = 0
        while district_memory.is_overused(primary_wall) and attempts < 5:
            primary_wall = self._get_weighted_variant(lib["structure"]["primary_wall"])
            attempts += 1
        district_memory.add_building(primary_wall)

        accent = self._get_weighted_variant(lib["structure"]["accent"])

        # FIX: accent_beam construction was producing malformed names.
        # Rule: if the accent is already a log block, the beam IS the accent.
        # Otherwise derive the stripped variant by prepending "stripped_".
        # This avoids "stripped_stripped_..." and handles all log name forms cleanly.
        if "_log" in accent:
            if accent.startswith("stripped_"):
                accent_beam = accent                          # already stripped
            else:
                accent_beam = f"stripped_{accent}"           # e.g. oak_log -> stripped_oak_log
        else:
            accent_beam = accent                             # non-log accent, use as-is

        palette: dict = {
            "archetype":   archetype,
            "wall":        f"minecraft:{primary_wall}",
            "foundation":  f"minecraft:{lib['structure']['foundation']}",
            "accent":      f"minecraft:{accent}",
            "accent_beam": f"minecraft:{accent_beam}",
            "roof_block":  f"minecraft:{lib['structure']['roof']['block']}",
            "roof_stairs": f"minecraft:{lib['structure']['roof']['stairs']}",
            "roof_slab":   f"minecraft:{lib['structure']['roof']['slab']}",
        }

        # Decor entries (lists or raw strings)
        for key, value in lib["structure"]["decor"].items():
            if isinstance(value, list):
                palette[key] = f"minecraft:{random.choice(value)}"
            else:
                palette[key] = f"minecraft:{value}"

        # Safe defaults for keys builders always expect
        if "door" not in palette:
            palette["door"] = "minecraft:oak_door"
            logger.debug("  [palette] 'door' missing — defaulting to oak_door")
        if "fence" not in palette:
            palette["fence"] = "minecraft:oak_fence"
            logger.debug("  [palette] 'fence' missing — defaulting to oak_fence")
        if "floor" not in palette:
            floor_val = (
                f"minecraft:{primary_wall}"
                if "_planks" in primary_wall
                else "minecraft:oak_planks"
            )
            palette["floor"] = floor_val
            logger.debug("  [palette] 'floor' missing — defaulting to %s", floor_val)
        if "interior_light" not in palette:
            palette["interior_light"] = "minecraft:pearlescent_froglight"
            logger.debug("  [palette] 'interior_light' missing — defaulting to pearlescent_froglight")

        # District-specific overrides
        district_data = lib["districts"].get(district_type, {})
        for k, v in district_data.items():
            if isinstance(v, list):
                palette[k] = f"minecraft:{random.choice(v)}"
            else:
                palette[k] = f"minecraft:{v}"

        return palette

    # ── Road helpers ────────────────────────────────────────────────────────

    # FIX: The original used a catch-all `endswith("s")` strip for plural->singular
    # conversion, which corrupted names like "packed_ice" -> "packed_ic".
    # Replaced with an explicit mapping covering all road-surface blocks that
    # appear in the library.
    _PLURAL_TO_SINGULAR: Dict[str, str] = {
        "stone_bricks":           "stone_brick",
        "deepslate_bricks":       "deepslate_brick",
        "prismarine_bricks":      "prismarine_brick",
        "mossy_stone_bricks":     "mossy_stone_brick",
        "mossy_cobblestone":      "mossy_cobblestone",   # no change needed
        "red_nether_bricks":      "red_nether_brick",
        # planks: strip "_planks" and use the wood type directly
        "oak_planks":             "oak",
        "spruce_planks":          "spruce",
        "dark_oak_planks":        "dark_oak",
        "acacia_planks":          "acacia",
        "jungle_planks":          "jungle",
        "cherry_planks":          "cherry",
    }

    def _to_singular(self, block: str) -> str:
        """Convert a block name to its singular/prefix form for stair/slab derivation."""
        return self._PLURAL_TO_SINGULAR.get(block, block)

    def get_road_component(
        self,
        biome_name: str,
        is_main: bool,
        component_type: str = "base",
        existing_block: str = None,
    ) -> str:
        """
        Return a road-related block for the given archetype.
        component_type: "base" | "stair" | "slab" | "edge"
        existing_block: pass the already-chosen base block to avoid re-randomising
                        (important for slab/stair to stay consistent with base).
        """
        archetype = self._resolve_archetype(biome_name)
        archetype_data = self.MATERIAL_LIBRARY.get(archetype, self.MATERIAL_LIBRARY["TEMPERATE"])
        road_cfg = archetype_data.get("roads", self.MATERIAL_LIBRARY["TEMPERATE"]["roads"])

        if component_type == "edge":
            return f"minecraft:{road_cfg.get('edge', 'cobblestone_slab')}"

        # Resolve or reuse the base block
        if existing_block:
            base_block = existing_block.replace("minecraft:", "")
        else:
            variant_data = road_cfg["main" if is_main else "path"]
            base_block = (
                self._get_weighted_variant(variant_data)
                if isinstance(variant_data, dict)
                else variant_data
            )

        if component_type == "base":
            return f"minecraft:{base_block}"

        singular = self._to_singular(base_block)

        if component_type == "stair":
            stair_key = f"{singular}_stairs"
            return (
                f"minecraft:{stair_key}"
                if self._block_exists(stair_key, base_block)
                else "minecraft:oak_stairs"
            )

        if component_type == "slab":
            slab_key = f"{singular}_slab"
            return (
                f"minecraft:{slab_key}"
                if self._block_exists(slab_key, base_block)
                else "minecraft:oak_slab"
            )

        raise ValueError(f"Unknown road component_type: {component_type!r}")

    def get_road_material(self, biome_name: str, is_main: bool = True) -> str:
        return self.get_road_component(biome_name, is_main, component_type="base")

    def _block_exists(self, key: str, base: str) -> bool:
        """
        Heuristic: certain block categories do not have stair/slab variants
        and should fall back to oak equivalents.
        """
        no_variants = {
            "dirt_path", "gravel", "grass_block", "coarse_dirt",
            "mud", "moss_block", "smooth_stone", "stone", "terracotta",
            "packed_ice", "snow_block", "red_terracotta",
        }
        if base in no_variants:
            return False
        invalid_categories = ["wool", "glass", "concrete", "powder", "ice", "leaves"]
        if any(cat in base for cat in invalid_categories):
            return False
        return True


# ── Module-level convenience helpers ────────────────────────────────────────

def palette_get(palette: dict, key: str, default: str = "minecraft:stone") -> str:
    """Safe getter with fallback for palette dicts."""
    return palette.get(key, default)


_FALLBACK_BIOME = "plains"


def get_biome_palette(biome_type: str = _FALLBACK_BIOME, district_id: int = 0) -> dict:
    """
    Compatibility wrapper for older code that called get_biome_palette() directly.
    Delegates to PaletteSystem.create_palette().
    """
    system = PaletteSystem()
    try:
        return system.create_palette(
            district_id=district_id,
            biome_name=biome_type,
            district_type="residential",
        )
    except Exception as e:
        logger.warning(
            "Error generating palette for %r (%s) — falling back to %r.",
            biome_type, str(e), _FALLBACK_BIOME,
        )
        return system.create_palette(
            district_id=district_id,
            biome_name=_FALLBACK_BIOME,
        )