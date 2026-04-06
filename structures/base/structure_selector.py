from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Callable

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette
from data.configurations import SettlementConfig
from data.settlement_entities import Plot
from world_interface.block_buffer import BlockBuffer

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
# Registry — single source of truth for all builder callables.
# Each entry: key → (builder_fn, min_width, min_depth)
# ---------------------------------------------------------------------------

_FACING_TO_ROTATION: dict[str, int] = {
    "north": 0,
    "east":  90,
    "south": 180,
    "west":  270,
}


def _rotation(plot) -> int:
    """Convert plot.facing to a clockwise rotation in degrees."""
    return _FACING_TO_ROTATION.get((plot.facing or "south").lower(), 0)


def _build_registry(analysis: WorldAnalysisResult | None = None) -> dict[str, tuple[Callable, int, int]]:

    def cottage(ed, pl, pal):
        from structures.house.house_grammar import HouseGrammar
        return HouseGrammar(
            ed, pal,
            scorer=_HOUSE_SCORER,
            ngram_scorer=_HOUSE_NGRAM_SCORER,
        ).build(pl, rotation=_rotation(pl))

    def blacksmith(ed, pl, pal):
        from structures.misc.blacksmith import Blacksmith
        return Blacksmith().build(ed, pl, pal, rotation=_rotation(pl))

    def dock(ed, pl, pal):
        from structures.misc.dock import Dock
        return Dock().build(ed, pl, pal, rotation=_rotation(pl))

    def market_stall(ed, pl, pal):
        from structures.misc.market_stall import MarketStall
        return MarketStall().build(ed, pl, pal, rotation=_rotation(pl))

    def clock_tower(ed, pl, pal):
        from structures.misc.clock_tower import ClockTower
        return ClockTower().build(ed, pl, pal, rotation=_rotation(pl))

    def tavern(ed, pl, pal):
        from structures.misc.tavern import Tavern
        return Tavern().build(ed, pl, pal, rotation=_rotation(pl))

    def tower(ed, pl, pal):
        from structures.tower.tower import Tower
        return Tower().build(ed, pl, pal, rotation=_rotation(pl))

    def spire_tower(ed, pl, pal):
        from structures.misc.spire_tower import SpireTower
        return SpireTower().build(ed, pl, pal, rotation=_rotation(pl), analysis=analysis)

    def fortification(ed, pl, pal):
        from structures.misc.fortification import Fortification
        return Fortification().build(ed, pl, pal)

    def plaza(ed, pl, pal):
        from structures.misc.square_centre import SquareCentre
        return SquareCentre().build(ed, pl, pal)

    def farm(_, pl, pal):
        from structures.farm.farm import Farm
        return Farm().build(pl, pal)

    def decoration(ed, pl, pal):
        from structures.decoration.plot.decoration import Decoration
        return Decoration().build(ed, pl, pal)

    # (builder_fn, min_width, min_depth)
    # Placement rules:
    #   - tower        → FortificationBuilder perimeter corners only
    #   - spire_tower  → placed once at best_area centroid (settlement_generator)
    #   - tower_house  → plot building inside settlement (included below)
    #   - fortification → FortificationBuilder perimeter only
    #   - dock         → placed once per fishing district (settlement_generator)
    #                    also available as a regular plot building in fishing districts
    return {
        "cottage":      (cottage,      7,  7),
        "tower_house":  (spire_tower, 10,  6),   # plot building — not fortification
        "blacksmith":   (blacksmith,   9,  8),
        "plaza":        (plaza,       10, 10),
        "market_stall": (market_stall, 5,  5),
        "clock_tower":  (clock_tower,  8,  8),
        "tavern":       (tavern,      12,  8),
        "farm":         (farm,         5,  5),
        "dock":         (dock,        14, 10),
        "decoration":   (decoration,   4,  4),
    }


# ---------------------------------------------------------------------------
# District pools
# ---------------------------------------------------------------------------

DISTRICT_POOLS: dict[str, dict[str, float]] = {
    "residential": {
        "cottage":       0.30,
        "tower_house":   0.08,
        "blacksmith":    0.16,
        "market_stall":  0.15,
        "clock_tower":   0.09,
        "tavern":        0.09,
        "farm":          0.13,
    },
    "farming": {
        "farm":          0.70,
        "market_stall":  0.30,
    },
    "fishing": {
        "dock":          0.42,
        "cottage":       0.26,
        "market_stall":  0.21,
        "clock_tower":   0.11,
    },
    "forest": {
        "clock_tower":   0.25,
        "cottage":       0.40,
        "tavern":        0.35,
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
      1. District pool lookup     — each district has a weighted pool.
      2. Plot size gate           — from the registry min sizes.
      3. Weighted random selection from eligible templates.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        config: SettlementConfig,
        palette: BiomePalette,
        has_water: bool = False,
    ) -> None:
        self.analysis  = analysis
        self.config    = config
        self.palette   = palette
        self.has_water = has_water
        self._registry = _build_registry(analysis=analysis)

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

        pool = dict(DISTRICT_POOLS.get(dtype, FALLBACK_POOL) or FALLBACK_POOL)

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

    def build(self, plot: Plot, template_key: str) -> BlockBuffer | None:
        """Execute the selected template on the plot. Returns a BlockBuffer or None on failure."""
        entry = self._registry.get(template_key)
        if entry is None:
            logger.warning("Unknown template key '%s' — skipping.", template_key)
            return None

        builder, _, _ = entry
        try:
            return builder(None, plot, self.palette)
        except Exception:
            logger.error(
                "Builder '%s' failed on plot (%d,%d) size %dx%d.",
                template_key, plot.x, plot.z, plot.width, plot.depth,
                exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

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