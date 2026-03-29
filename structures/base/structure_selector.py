from __future__ import annotations

import logging
import random

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette
from data.configurations import SettlementConfig
from data.settlement_entities import Plot
from structures.base.structure_agent import StructureAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline terrain check agent — module-level so it isn't recreated per call
# ---------------------------------------------------------------------------

class _QuickAgent(StructureAgent):
    """Lightweight terrain check without a full StructureAgent subclass."""
    def decide(self, plot: Plot) -> dict:
        patch = self.extract_patch(plot)
        return {"build": self.is_flat(patch, tolerance=3)}


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

def _load_templates() -> dict:
    from structures.base.templates import (
        BlacksmithTemplate,
        MarketStallTemplate,
        SimpleCottageTemplate,
        SquareCentreTemplate,
        TowerHouseTemplate,
    )
    return {
        "cottage":      SimpleCottageTemplate(),
        "tower_house":  TowerHouseTemplate(),
        "blacksmith":   BlacksmithTemplate(),
        "plaza":        SquareCentreTemplate(),
        "market_stall": MarketStallTemplate(),
    }


class StructureSelector:
    """
    Single decision point for choosing what to build on a plot.

    Decision layers (in order):
      1. District type hard rules  — farming always gets a farm, etc.
      2. Terrain agent check       — is the plot actually buildable?
      3. Plot size gate            — templates have minimum size requirements.
      4. Weighted random selection — from the eligible template pool.
    """

    MIN_SIZE: dict[str, tuple[int, int]] = {
        "cottage":      (6,  6),
        "tower_house":  (8,  8),
        "blacksmith":   (8,  6),
        "plaza":        (10, 10),
        "market_stall": (5,  5),
    }

    DISTRICT_POOLS: dict[str, dict[str, float]] = {
        "residential": {
            "cottage":      0.5,
            "tower_house":  0.3,
            "market_stall": 0.2,
        },
        "farming": {},
        "fishing": {
            "cottage":      0.7,
            "market_stall": 0.3,
        },
        "forest": {},
    }

    FALLBACK_POOL: dict[str, float] = {
        "cottage":      0.6,
        "market_stall": 0.4,
    }

    def __init__(
        self,
        editor,
        analysis: WorldAnalysisResult,
        config: SettlementConfig,
        palette: BiomePalette,
        has_water: bool = False,
    ) -> None:
        self.editor    = editor
        self.analysis  = analysis
        self.config    = config
        self.palette   = palette
        self.has_water = has_water
        self._templates = _load_templates()
        self._agent = _QuickAgent(analysis)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def select(self, plot: Plot) -> str | None:
        """
        Return the template key to build on this plot, or None to skip.

        Returns None if:
          - The district type triggers a hard skip
          - The terrain agent rejects the plot
          - No eligible template fits the plot size
        """
        dtype = (plot.type or "residential").strip().lower()

        if dtype == "farming":
            return "farm"
        if dtype == "forest":
            return "decoration"
        if dtype == "fishing" and not self.has_water:
            dtype = "residential"

        if not self._terrain_ok(plot):
            logger.debug("Plot (%d,%d) rejected by terrain agent.", plot.x, plot.z)
            return None

        pool = self.DISTRICT_POOLS.get(dtype, self.FALLBACK_POOL) or self.FALLBACK_POOL
        eligible = {
            key: weight for key, weight in pool.items()
            if self._fits(plot, key)
        }

        if not eligible:
            logger.debug(
                "Plot (%d,%d) size %dx%d — no eligible template for district '%s'.",
                plot.x, plot.z, plot.width, plot.depth, dtype,
            )
            return None

        return self._weighted_choice(eligible)

    def build(self, plot: Plot, template_key: str) -> None:
        """
        Execute the selected template on the plot.

        For non-template keys ('farm', 'decoration') the caller handles
        placement via the existing Structure subclasses.
        """
        template = self._templates.get(template_key)
        if template is None:
            logger.warning("Unknown template key '%s' — skipping.", template_key)
            return

        template.build(
            self.editor,
            plot.x, plot.y, plot.z,
            plot.width, plot.depth,
            self.palette,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _terrain_ok(self, plot: Plot) -> bool:
        return self._agent.decide(plot).get("build", False)

    def _fits(self, plot: Plot, key: str) -> bool:
        min_w, min_d = self.MIN_SIZE.get(key, (4, 4))
        return plot.width >= min_w and plot.depth >= min_d

    @staticmethod
    def _weighted_choice(pool: dict[str, float]) -> str:
        keys   = list(pool.keys())
        weights = list(pool.values())
        total  = sum(weights)
        r      = random.random() * total
        cumulative = 0.0
        for key, w in zip(keys, weights):
            cumulative += w
            if r <= cumulative:
                return key
        return keys[-1]