from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Callable

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette
from data.configurations import SettlementConfig
from data.settlement_entities import Plot
from structures.base.structure_agent import StructureAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scorer singletons
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_PATH = (
    Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"
)

def _load_house_scorers():
    from structures.house.house_scorer import HouseScorer
    from structures.house.house_ngram_scorer import HouseNgramScorer
    scorer       = HouseScorer.load(_DEFAULT_MODEL_PATH)
    ngram_scorer = HouseNgramScorer.load(_DEFAULT_MODEL_PATH.parent / "house_ngram.pkl")
    return scorer, ngram_scorer

try:
    _HOUSE_SCORER, _HOUSE_NGRAM_SCORER = _load_house_scorers()
except Exception as e:
    logger.warning("Could not pre-load house scorers: %s — will load on demand.", e)
    _HOUSE_SCORER       = None
    _HOUSE_NGRAM_SCORER = None


# ---------------------------------------------------------------------------
# Terrain agent
# ---------------------------------------------------------------------------

class _QuickAgent(StructureAgent):
    """Lightweight terrain check without a full StructureAgent subclass."""
    def decide(self, plot: Plot) -> dict:
        patch = self.extract_patch(plot)
        return {"build": self.is_flat(patch, tolerance=4)}   # FIX 5: loosened from 3→4


# ---------------------------------------------------------------------------
# FIX 3: Registry — single source of truth for all builder callables.
# Each entry: key → (builder_fn, min_width, min_depth)
# ---------------------------------------------------------------------------

def _build_registry() -> dict[str, tuple[Callable, int, int]]:

    def cottage(ed, pl, pal):
        from structures.house.house_grammar import HouseGrammar
        HouseGrammar(
            ed, pal,
            scorer=_HOUSE_SCORER,
            ngram_scorer=_HOUSE_NGRAM_SCORER,
        ).build(pl)

    def blacksmith(ed, pl, pal):
        from structures.misc.blacksmith import Blacksmith
        Blacksmith().build(ed, pl, pal)

    def market_stall(ed, pl, pal):
        from structures.misc.market_stall import MarketStall
        MarketStall().build(ed, pl, pal)

    def clock_tower(ed, pl, pal):
        from structures.misc.clock_tower import ClockTower
        ClockTower().build(ed, pl, pal)

    def tavern(ed, pl, pal):
        from structures.misc.tavern import Tavern
        Tavern().build(ed, pl, pal)

    def tower(ed, pl, pal):
        from structures.tower.tower import Tower
        Tower().build(ed, pl, pal)

    def spire_tower(ed, pl, pal):
        from structures.misc.spire_tower import SpireTower
        SpireTower().build(ed, pl, pal)

    def fortification(ed, pl, pal):
        from structures.misc.fortification import Fortification
        Fortification().build(ed, pl, pal)

    def plaza(ed, pl, pal):
        from structures.misc.square_centre import SquareCentre
        SquareCentre().build(ed, pl, pal)

    def farm(ed, pl, pal):
        from structures.farm.farm import Farm
        Farm().build(ed, pl, pal)

    def decoration(ed, pl, pal):
        from structures.decoration.plot.decoration import Decoration
        Decoration().build(ed, pl, pal)

    # (builder_fn, min_width, min_depth)
    # Placement rules:
    #   - tower        → FortificationBuilder perimeter corners only
    #   - spire_tower  → placed once at best_area centroid (settlement_generator)
    #   - tower_house  → plot building inside settlement (included below)
    #   - fortification → FortificationBuilder perimeter only
    return {
        "cottage":      (cottage,      6,  6),
        "tower_house":  (spire_tower, 10,  6),   # plot building — not fortification
        "blacksmith":   (blacksmith,   8,  6),
        "plaza":        (plaza,       10, 10),
        "market_stall": (market_stall, 5,  5),
        "clock_tower":  (clock_tower,  8,  8),
        "tavern":       (tavern,      12,  8),
        "farm":         (farm,         5,  5),
        "decoration":   (decoration,   4,  4),
    }


# ---------------------------------------------------------------------------
# District pools
# ---------------------------------------------------------------------------

# FIX 1a: forest gets variety — towers, cottages, decorations
# FIX 1b: farming gets variety — farms + market stalls + decorations
# FIX 4:  fishing adds clock_tower and decoration alongside cottage/stall

DISTRICT_POOLS: dict[str, dict[str, float]] = {
    "residential": {
        "cottage":       0.35,
        "tower_house":   0.10,
        "blacksmith":    0.18,
        "market_stall":  0.17,
        "clock_tower":   0.10,
        "tavern":        0.10,
    },
    "farming": {
        "farm":          0.60,
        "market_stall":  0.25,
        "decoration":    0.15,
    },
    "fishing": {
        "cottage":       0.45,
        "market_stall":  0.30,
        "clock_tower":   0.15,
        "decoration":    0.10,
    },
    "forest": {
        "decoration":    0.40,
        "clock_tower":   0.20,
        "cottage":       0.25,
        "tavern":        0.15,
    },
}

FALLBACK_POOL: dict[str, float] = {
    "cottage":      0.60,
    "market_stall": 0.40,
}


# ---------------------------------------------------------------------------
# StructureSelector
# ---------------------------------------------------------------------------

class StructureSelector:
    """
    Single decision point for choosing what to build on a plot.

    Decision layers (in order):
      1. District pool lookup     — each district now has a weighted pool
                                    (no more hard-routing farming/forest).
      2. Terrain agent check      — is the plot actually buildable?
      3. Plot size gate           — from the registry min sizes.
      4. Weighted random selection from eligible templates.
    """

    def __init__(
        self,
        editor,
        analysis: WorldAnalysisResult,
        config: SettlementConfig,
        palette: BiomePalette,
        has_water: bool = False,
        fountain_district_ids: set[int] | None = None,
    ) -> None:
        self.editor               = editor
        self.analysis             = analysis
        self.config               = config
        self.palette              = palette
        self.has_water            = has_water
        # Districts that already have a fountain at their centre — decoration
        # is suppressed for these so the fountain area stays clear.
        self.fountain_district_ids: set[int] = fountain_district_ids or set()
        self._registry = _build_registry()
        self._agent    = _QuickAgent(analysis)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def select(self, plot: Plot) -> str | None:
        """
        Return the template key to build on this plot, or None to skip.
        """
        dtype = (plot.type or "residential").strip().lower()

        # fishing with no water access falls back to residential
        if dtype == "fishing" and not self.has_water:
            dtype = "residential"

        if not self._terrain_ok(plot):
            logger.debug("Plot (%d,%d) rejected by terrain agent.", plot.x, plot.z)
            return None

        pool = dict(DISTRICT_POOLS.get(dtype, FALLBACK_POOL) or FALLBACK_POOL)

        # Suppress decoration for districts that already have a fountain —
        # the centroid area is taken and decoration would crowd it.
        if hasattr(plot, "district_id") and plot.district_id in self.fountain_district_ids:
            pool.pop("decoration", None)

        eligible = {
            key: weight
            for key, weight in pool.items()
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
        """Execute the selected template on the plot."""
        entry = self._registry.get(template_key)
        if entry is None:
            logger.warning("Unknown template key '%s' — skipping.", template_key)
            return

        builder, _, _ = entry
        try:
            builder(self.editor, plot, self.palette)
        except Exception:
            logger.error(
                "Builder '%s' failed on plot (%d,%d) size %dx%d.",
                template_key, plot.x, plot.z, plot.width, plot.depth,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _terrain_ok(self, plot: Plot) -> bool:
        return self._agent.decide(plot).get("build", False)

    def _fits(self, plot: Plot, key: str) -> bool:
        entry = self._registry.get(key)
        if entry is None:
            return False
        _, min_w, min_d = entry
        return plot.width >= min_w and plot.depth >= min_d

    @staticmethod
    def _weighted_choice(pool: dict[str, float]) -> str:
        keys    = list(pool.keys())
        weights = list(pool.values())
        total   = sum(weights)
        r       = random.random() * total
        cumulative = 0.0
        for key, w in zip(keys, weights):
            cumulative += w
            if r <= cumulative:
                return key
        return keys[-1]