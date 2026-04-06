"""
palette/palette_system.py
--------------------------
Archetype-driven palette + road system with anti-clustering district memory.

This is a standalone palette system that lives alongside data/palette_system.py.
  - data/palette_system.py  — integrated into settlement_generator, returns BiomePalette
  - palette/palette_system.py — archetype-based, used by Bridge and other ad-hoc builders

Key differences:
  • Biome → archetype resolution (TEMPERATE, FROZEN, ARID, LUSH, AQUATIC, SAVANNA,
    BADLANDS, CHERRY_GROVE) via keyword matching — handles vanilla and modded biomes.
  • create_palette() returns a plain dict with "wall", "foundation", "road_main", etc.
  • get_road_component() resolves the correct stair/slab variant for road blocks.
"""
from __future__ import annotations

import logging
import random
from collections import deque
from typing import Dict

from palette.material_library import MATERIAL_LIBRARY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# District memory — prevents adjacent buildings from using identical materials
# ---------------------------------------------------------------------------

class DistrictMemory:
    """Tracks materials used in a district for anti-clustering."""

    def __init__(self, district_id: int, history_length: int = 3) -> None:
        self.district_id = district_id
        self.history: deque[str] = deque(maxlen=history_length)

    def add_building(self, material: str) -> None:
        self.history.append(material)

    def is_overused(self, material: str) -> bool:
        return material in self.history


# ---------------------------------------------------------------------------
# PaletteSystem
# ---------------------------------------------------------------------------

class PaletteSystem:
    """
    Environment-aware, archetype-driven palette system with road support.

    Usage
    -----
        ps  = PaletteSystem()
        pal = ps.create_palette(temp=0.7, downfall=0.5,
                                district_id=1, biome_name="minecraft:plains")
        # pal["wall"], pal["foundation"], pal["road_main"], ...

        road_block = ps.get_road_component("minecraft:taiga", is_main=True,
                                           component_type="stair")
    """

    def __init__(self) -> None:
        self._district_memories: Dict[int, DistrictMemory] = {}

    # ------------------------------------------------------------------
    # Biome → archetype
    # ------------------------------------------------------------------

    def _resolve_archetype(self, biome_name: str = "") -> str:
        """
        Map a raw biome name to a material archetype using priority-ordered
        keyword matching.  Handles vanilla and modded biomes.
        """
        name = biome_name.lower().replace("minecraft:", "")

        # 1. Specific biomes with distinct aesthetics
        if "savanna"  in name: return "SAVANNA"
        if "badlands" in name or "mesa" in name: return "BADLANDS"
        if "cherry"   in name: return "CHERRY_GROVE"

        # 2. Climate groups
        if any(w in name for w in ["ice", "snow", "frozen", "taiga", "slopes", "jagged"]):
            return "FROZEN"
        if any(w in name for w in ["desert", "dunes"]):
            return "ARID"
        if any(w in name for w in ["jungle", "swamp", "mangrove", "bamboo"]):
            return "LUSH"
        if any(w in name for w in ["ocean", "river", "beach", "coast"]):
            return "AQUATIC"

        # 3. Default — plains, forest, meadow, birch forest, …
        return "TEMPERATE"

    # ------------------------------------------------------------------
    # District memory helpers
    # ------------------------------------------------------------------

    def _get_or_create_district(self, district_id: int) -> DistrictMemory:
        if district_id not in self._district_memories:
            self._district_memories[district_id] = DistrictMemory(district_id)
        return self._district_memories[district_id]

    # ------------------------------------------------------------------
    # Weighted variant picker
    # ------------------------------------------------------------------

    @staticmethod
    def _weighted_variant(variant_data: dict) -> str:
        return random.choices(
            variant_data["variants"],
            weights=variant_data["weights"],
            k=1,
        )[0]

    # ------------------------------------------------------------------
    # Core palette creation
    # ------------------------------------------------------------------

    def create_palette(
        self,
        temp:          float = 0.5,
        downfall:      float = 0.5,
        district_id:   int   = 0,
        biome_name:    str   = "",
        district_type: str   = "residential",
    ) -> dict:
        """
        Return a material dict for a single building / district slot.

        Keys include: wall, foundation, frame, roof_block, roof_stairs,
        roof_slab, door, window, fence, light, road_main, road_edge.
        """
        archetype = self._resolve_archetype(biome_name)
        lib       = MATERIAL_LIBRARY[archetype]
        memory    = self._get_or_create_district(district_id)

        # Primary wall with anti-clustering re-roll
        primary_wall = self._weighted_variant(lib["structure"]["primary_wall"])
        for _ in range(5):
            if not memory.is_overused(primary_wall):
                break
            primary_wall = self._weighted_variant(lib["structure"]["primary_wall"])
        memory.add_building(primary_wall)

        def mc(block: str) -> str:
            return block if block.startswith("minecraft:") else f"minecraft:{block}"

        struct = lib["structure"]
        road   = lib.get("roads", {})

        palette: dict = {
            "wall":        mc(primary_wall),
            "foundation":  mc(struct["foundation"]),
            "frame":       mc(struct["frame"]),
            "roof_block":  mc(struct["roof"]["block"]),
            "roof_stairs": mc(struct["roof"]["stairs"]),
            "roof_slab":   mc(struct["roof"]["slab"]),
        }

        # Decor keys
        for key, value in struct.get("decor", {}).items():
            palette[key] = mc(random.choice(value) if isinstance(value, list) else value)

        # District-specific overrides
        for k, v in lib.get("districts", {}).get(district_type, {}).items():
            palette[k] = mc(random.choice(v) if isinstance(v, list) else v)

        # Road materials
        if road:
            main_data = road.get("main", {})
            path_data = road.get("path", {})
            palette["road_main"] = mc(
                self._weighted_variant(main_data)
                if isinstance(main_data, dict)
                else main_data
            )
            palette["road_path"] = mc(
                self._weighted_variant(path_data)
                if isinstance(path_data, dict)
                else path_data
            )
            palette["road_edge"] = mc(road.get("edge", "cobblestone_slab"))

        return palette

    # ------------------------------------------------------------------
    # Road component helpers
    # ------------------------------------------------------------------

    def get_road_component(
        self,
        biome_name:     str,
        is_main:        bool,
        component_type: str = "base",
        existing_block: str | None = None,
    ) -> str:
        """
        Return the road block, stair, slab, or edge for a biome + road type.

        component_type: "base" | "stair" | "slab" | "edge"
        """
        archetype     = self._resolve_archetype(biome_name)
        lib           = MATERIAL_LIBRARY.get(archetype, MATERIAL_LIBRARY["TEMPERATE"])
        road_cfg      = lib.get("roads", MATERIAL_LIBRARY["TEMPERATE"]["roads"])

        if existing_block:
            base_block = existing_block.replace("minecraft:", "")
        else:
            variant_data = road_cfg["main" if is_main else "path"]
            base_block = (
                self._weighted_variant(variant_data)
                if isinstance(variant_data, dict)
                else variant_data
            )

        if component_type == "edge":
            return f"minecraft:{road_cfg.get('edge', 'cobblestone_slab')}"
        if component_type == "base":
            return f"minecraft:{base_block}"

        # Derive stair / slab key from the base block name
        clean = base_block
        if "planks"   in clean: clean = clean.replace("_planks", "").replace("planks", "")
        elif "bricks"  in clean: clean = clean.replace("bricks", "brick")
        elif clean == "bricks":  clean = "brick"
        elif clean.endswith("s") and not clean.endswith("ss"): clean = clean[:-1]

        if component_type == "stair":
            key = f"{clean}_stairs"
            return f"minecraft:{key}" if self._stair_slab_exists(key, base_block) else "minecraft:oak_stairs"
        if component_type == "slab":
            key = f"{clean}_slab"
            return f"minecraft:{key}"  if self._stair_slab_exists(key, base_block) else "minecraft:oak_slab"

        raise ValueError(f"Unknown road component type: {component_type!r}")

    def get_road_material(self, biome_name: str, is_main: bool = True) -> str:
        return self.get_road_component(biome_name, is_main, component_type="base")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stair_slab_exists(key: str, base: str) -> bool:
        """Return False for blocks that have no stair/slab variants."""
        no_variants = {
            "dirt_path", "gravel", "grass_block", "coarse_dirt", "mud",
            "moss_block", "smooth_stone", "stone", "terracotta",
        }
        if base in no_variants:
            return False
        for cat in ("wool", "glass", "concrete", "powder", "ice", "leaves"):
            if cat in base:
                return False
        return True
