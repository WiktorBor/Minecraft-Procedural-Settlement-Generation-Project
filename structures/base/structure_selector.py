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
# Scorer singletons — loaded once per process, shared across all selectors
# ---------------------------------------------------------------------------
# HouseScorer and HouseNgramScorer each do a pickle.load() from disk.
# Loading them inside HouseGrammar.__init__ (which runs per house) caused
# them to be re-read on every single cottage build.  We load them here at
# import time so every StructureSelector instance shares the same objects.

_DEFAULT_MODEL_PATH = (
    Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"
)

def _load_house_scorers():
    """Load scorer singletons once; return (HouseScorer, HouseNgramScorer)."""
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
        return {"build": self.is_flat(patch, tolerance=3)}


# ---------------------------------------------------------------------------
# Builder registry
# ---------------------------------------------------------------------------
# Each callable has signature  (editor, plot: Plot, palette: BiomePalette) -> None
# Imports are deferred so unused structure modules are never loaded at startup.

def _builders() -> dict[str, Callable]:

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

    return {
        "cottage":       cottage,
        "tower":         tower,
        "tower_house":   spire_tower,
        "blacksmith":    blacksmith,
        "plaza":         plaza,
        "market_stall":  market_stall,
        "clock_tower":   clock_tower,
        "tavern":        tavern,
        "spire_tower":   spire_tower,
        "fortification": fortification,
        "farm":          farm,
        "decoration":    decoration,
    }


# ---------------------------------------------------------------------------
# StructureSelector
# ---------------------------------------------------------------------------

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
        "cottage":       (6,  6),
        "tower":         (7,  7),
        "tower_house":   (10, 6),
        "blacksmith":    (8,  6),
        "plaza":         (10, 10),
        "market_stall":  (5,  5),
        "clock_tower":   (8,  8),
        "tavern":        (20, 12),
        "spire_tower":   (10, 6),
        "fortification": (5,  5),
        "farm":          (5,  5),
        "decoration":    (4,  4),
    }

    DISTRICT_POOLS: dict[str, dict[str, float]] = {
        "residential": {
            "cottage":       0.30,
            "tower":         0.10,
            "tower_house":   0.12,
            "spire_tower":   0.10,
            "blacksmith":    0.10,
            "market_stall":  0.10,
            "plaza":         0.08,
            "clock_tower":   0.06,
            "tavern":        0.04,
            "fortification": 0.10,
        },
        "farming": {},   # hard-routed to "farm" in select()
        "fishing": {
            "cottage":      0.7,
            "market_stall": 0.3,
        },
        "forest": {},    # hard-routed to "decoration" in select()
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
        self.editor     = editor
        self.analysis   = analysis
        self.config     = config
        self.palette    = palette
        self.has_water  = has_water
        # Bug fix: was calling _load_templates() which didn't exist.
        # The builder registry is _builders().
        self._templates = _builders()
        self._agent     = _QuickAgent(analysis)

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

        Bug fix: the old signature passed (editor, x, y, z, w, d, palette)
        but every builder in _builders() expects (editor, plot, palette).
        Now passes the Plot object directly.
        """
        builder = self._templates.get(template_key)
        if builder is None:
            logger.warning("Unknown template key '%s' — skipping.", template_key)
            return

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