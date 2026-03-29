"""
planning/palette_mapper.py
--------------------------
Intelligent per-district palette generation implementing five coherence
principles:

  1. Material family   — all blocks drawn from the same biome/cultural context
  2. Role hierarchy    — primary (walls/floor), secondary (stone), accent, detail
  3. Color temperature — consistently warm or cool within each district
  4. Value range       — spans light, medium, dark for visual depth
  5. Anti-clustering   — adjacent districts avoid sharing the same primary material

The raw material pools are defined in data/material_families.py.
The output type BiomePalette is defined in data/biome_palettes.py.

Usage
-----
    mapper = PaletteMapper(analysis, districts, seed=42)
    palettes = mapper.generate()       # dict[int, BiomePalette]
    palette  = palettes[district_idx]
"""
from __future__ import annotations

import random
from collections import Counter

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette
from data.material_families import (
    BIOME_ID_MAP,
    BLOCK_VALUES,
    COOL_STONES,
    COOL_WOODS,
    MATERIAL_FAMILIES,
    NEUTRAL_STONES,
    WARM_STONES,
    WARM_WOODS,
)
from data.settlement_entities import Districts


class PaletteMapper:
    """
    Generates per-district block palettes with five coherence principles.
    See module docstring for details.
    """

    def __init__(
        self,
        analysis:  WorldAnalysisResult,
        districts: Districts,
        seed:      int | None = None,
    ) -> None:
        self.analysis  = analysis
        self.districts = districts

        if seed is not None:
            random.seed(seed)

        self.district_biomes:   dict[int, str]        = {}
        self.district_palettes: dict[int, BiomePalette] = {}

        # Principle 5: track primary materials for anti-clustering
        self._district_primary_materials: dict[int, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> dict[int, BiomePalette]:
        """Generate all district palettes and return them."""
        self._compute_district_biomes()
        self._generate_palettes()
        return self.district_palettes

    def dominant_biome(self) -> str:
        """Return the most common biome name across all districts."""
        if not self.district_biomes:
            return "plains"
        return Counter(self.district_biomes.values()).most_common(1)[0][0]

    # ------------------------------------------------------------------
    # Biome resolution
    # ------------------------------------------------------------------

    def _compute_district_biomes(self) -> None:
        """Determine the dominant biome for each district."""
        flat_d = self.districts.map.ravel()
        flat_b = self.analysis.biomes.ravel()
        for idx in range(len(self.districts.types)):
            biome_ids = flat_b[flat_d == idx]
            if len(biome_ids) == 0:
                continue
            most_common = Counter(biome_ids).most_common(1)[0][0]
            self.district_biomes[idx] = self._biome_id_to_name(most_common)

    def _biome_id_to_name(self, biome: int | str) -> str:
        """
        Resolve a biome value to a canonical name string.

        Accepts either:
        - a string such as "minecraft:plains" (strips the namespace prefix), or
        - a legacy integer biome ID looked up in BIOME_ID_MAP.
        Falls back to "plains" when the ID is not recognised.
        """
        if isinstance(biome, str):
            return biome.replace("minecraft:", "").lower()
        return BIOME_ID_MAP.get(int(biome), "plains")

    # ------------------------------------------------------------------
    # Palette generation
    # ------------------------------------------------------------------

    def _generate_palettes(self) -> None:
        for idx, dtype in self.districts.types.items():
            biome = self.district_biomes.get(idx, "plains")
            self.district_palettes[idx] = self._generate_palette(biome, dtype, idx)

    def _generate_palette(
        self,
        biome:         str,
        district_type: str,
        district_idx:  int,
    ) -> BiomePalette:
        family = MATERIAL_FAMILIES.get(biome, MATERIAL_FAMILIES["plains"])

        primary_wood   = random.choice(family["primary_wood"])
        secondary_wood = random.choice(family["secondary_wood"])
        primary_stone  = random.choice(family["primary_stone"])
        accent         = self._ensure_value_range(
            family["accent_blocks"],
            [primary_wood, primary_stone],
        )

        # Principle 3: enforce temperature consistency
        if not self._is_temperature_consistent(primary_wood, primary_stone):
            primary_stone = self._rotate_to_temperature(
                family["primary_stone"],
                "warm" if self._is_warm(primary_wood) else "cool",
            )

        # Principle 5: anti-clustering
        primary_wood = self._enforce_color_variety(district_idx, primary_wood, biome)
        self._district_primary_materials[district_idx] = primary_wood

        # Principle 2: district-role overrides
        wall, secondary, roof_base = self._district_role_override(
            district_type, primary_wood, secondary_wood, primary_stone
        )

        def block(base: str, suffix: str) -> str:
            """Build a minecraft: block ID, avoiding duplicate suffixes."""
            if suffix in base:
                return f"minecraft:{base}"
            return f"minecraft:{base}_{suffix}"

        return {  # type: ignore[return-value]
            "wall":           block(wall, "planks"),
            "wall_secondary": f"minecraft:{secondary}",
            "foundation":     f"minecraft:{primary_stone}",
            "floor":          block(primary_wood, "planks"),
            "roof":           block(roof_base, "stairs"),
            "roof_slab":      block(roof_base, "slab"),
            "door":           block(primary_wood, "door"),
            "fence":          block(primary_wood, "fence"),
            "accent":         f"minecraft:{accent}",
            "accent_beam":    f"minecraft:stripped_{primary_wood}_log",
            "window":         "minecraft:glass_pane",
            "light":          "minecraft:lantern",
            "path":           self._pick_path(biome),
        }

    # ------------------------------------------------------------------
    # Principle 2: role hierarchy / district overrides
    # ------------------------------------------------------------------

    def _district_role_override(
        self,
        district_type:  str,
        primary_wood:   str,
        secondary_wood: str,
        primary_stone:  str,
    ) -> tuple[str, str, str]:
        """Return (wall_material, secondary_material, roof_base) for a district type."""
        if district_type in ("fortress", "watchtower"):
            return "stone_bricks", primary_stone, "stone_brick"
        if district_type == "market":
            return primary_wood, primary_stone, primary_wood
        if district_type == "temple":
            return primary_wood, primary_stone, "stone_brick"
        if district_type == "town_square":
            return primary_stone, "stone_bricks", "stone_brick"
        # residential / farming / fishing / forest → wooden domestic
        return primary_wood, secondary_wood, primary_wood

    # ------------------------------------------------------------------
    # Principle 3: color temperature
    # ------------------------------------------------------------------

    def _is_warm(self, material: str) -> bool:
        return any(w in material for w in WARM_WOODS + WARM_STONES)

    def _is_temperature_consistent(self, wood: str, stone: str) -> bool:
        if stone in NEUTRAL_STONES:
            return True
        return self._is_warm(wood) == self._is_warm(stone)

    def _rotate_to_temperature(self, stone_pool: list[str], temperature: str) -> str:
        if temperature == "warm":
            matches = [s for s in stone_pool if self._is_warm(s)]
        else:
            matches = [s for s in stone_pool if
                       any(c in s for c in COOL_WOODS + COOL_STONES)
                       or s in NEUTRAL_STONES]
        return random.choice(matches) if matches else stone_pool[0]

    # ------------------------------------------------------------------
    # Principle 4: value range
    # ------------------------------------------------------------------

    def _ensure_value_range(
        self,
        accent_pool:        list[str],
        existing_materials: list[str],
    ) -> str:
        values = [BLOCK_VALUES.get(m, "medium") for m in existing_materials]
        counts = Counter(values)
        if counts.get("dark", 0) == 0:
            dark = [a for a in accent_pool if BLOCK_VALUES.get(a, "medium") == "dark"]
            if dark:
                return random.choice(dark)
        if counts.get("light", 0) == 0:
            light = [a for a in accent_pool if BLOCK_VALUES.get(a, "medium") == "light"]
            if light:
                return random.choice(light)
        return random.choice(accent_pool)

    # ------------------------------------------------------------------
    # Principle 5: anti-clustering
    # ------------------------------------------------------------------

    def _enforce_color_variety(
        self,
        district_idx:     int,
        primary_material: str,
        biome:            str,
    ) -> str:
        recent = list(self._district_primary_materials.values())[-3:]
        if primary_material not in recent:
            return primary_material
        family = MATERIAL_FAMILIES.get(biome, MATERIAL_FAMILIES["plains"])
        alternatives = [
            m for m in family.get("primary_wood", [primary_material])
            if m != primary_material
        ]
        return random.choice(alternatives) if alternatives else primary_material

    # ------------------------------------------------------------------
    # Material helpers
    # ------------------------------------------------------------------

    def _pick_path(self, biome: str) -> str:
        if biome in ("forest", "taiga", "jungle"):
            return "minecraft:coarse_dirt"
        if biome == "desert":
            return "minecraft:sand"
        return "minecraft:dirt_path"