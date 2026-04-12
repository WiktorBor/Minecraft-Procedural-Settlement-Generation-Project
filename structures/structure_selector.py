"""
structures/placement/structure_selector.py
-------------------------------------------
Single decision point for choosing what to build on a plot and executing it.

Decision layers (in order):
  1. District pool lookup     — each district has a weighted pool.
  2. Plot size gate           — from the registry min sizes.
  3. Weighted random selection from eligible templates.

Rotation contract
-----------------
All grammar builders are called with NO rotation argument. They build
axis-aligned (door on local-north face). After build() returns a
BlockBuffer, this class applies rotate_buffer() from core/buffer_transform
if the plot requires a non-zero facing.

This means:
  - No grammar needs to know about rotation.
  - No BuildContext carries rotation state.
  - The bug where Ctx vs BuildContext caused mismatched transforms
    cannot happen — there is nothing to mismatch.
"""
from __future__ import annotations

import logging
import random
from typing import Callable

from data.analysis_results import WorldAnalysisResult
from palette.palette_system import PaletteSystem
from data.configurations import SettlementConfig
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.buffer_transform import facing_to_rotation, rotate_buffer
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry — single source of truth for all builder callables.
# Each entry: key → (builder_fn, min_width, min_depth)
#
# builder_fn signature: (plot: Plot, palette: PaletteSystem) -> BlockBuffer
# All builders are axis-aligned — NO rotation argument.
# ---------------------------------------------------------------------------

def _make_ctx(pal: PaletteSystem) -> tuple[BuildContext, BlockBuffer]:
    buf = BlockBuffer()
    return BuildContext(buffer=buf, palette=pal), buf


def _build_registry(analysis: WorldAnalysisResult | None = None) -> dict[str, tuple[Callable, int, int]]:

    def cottage(pl, pal):
        from structures.orchestrators.house import build_house_settlement
        ctx, buf = _make_ctx(pal)
        build_house_settlement(ctx, pl, pal)
        return buf

    def blacksmith(pl, pal):
        from structures.orchestrators.blacksmith import build_blacksmith
        ctx, buf = _make_ctx(pal)
        build_blacksmith(ctx, pl, pal)
        return buf

    def dock(pl, pal):
        from structures.orchestrators.dock import build_dock
        ctx, buf = _make_ctx(pal)
        build_dock(ctx, pl)
        return buf

    def market_stall(pl, pal):
        from structures.orchestrators.market import build_market_stall
        ctx, buf = _make_ctx(pal)
        build_market_stall(ctx, pl)
        return buf

    def clock_tower(pl, pal):
        from structures.orchestrators.tower import build_tower
        return build_tower(pal, pl.x, pl.y, pl.z, pl.width, 12, pl.depth, structure_role="clock_tower")

    def tavern(pl, pal):
        from structures.orchestrators.tavern import build_tavern
        ctx, buf = _make_ctx(pal)
        build_tavern(ctx, pl)
        return buf

    def spire_tower(pl, pal):
        from structures.orchestrators.spire_tower import build_spire_tower
        ctx, buf = _make_ctx(pal)
        build_spire_tower(ctx, pl, pal)
        return buf

    def plaza(pl, pal):
        from structures.orchestrators.plaza import build_square_centre
        ctx, buf = _make_ctx(pal)
        build_square_centre(ctx, pl)
        return buf

    def farm(pl, pal):
        from structures.farm.farm import Farm
        return Farm().build(pl, pal)

    def decoration(pl, pal):
        from structures.decoration.plot.decoration import Decoration
        return Decoration().build(pl, pal)

    # (builder_fn, min_width, min_depth)
    return {
        "cottage":      (cottage,      7,  7),
        "tower_house":  (spire_tower, 10,  6),
        "blacksmith":   (blacksmith,   9,  8),
        "plaza":        (plaza,       10, 10),
        "market_stall": (market_stall, 5,  5),
        "clock_tower":  (clock_tower,  8,  8),
        "tavern":       (tavern,      19,  8),
        "farm":         (farm,         5,  5),
        "dock":         (dock,        14, 10),
        "decoration":   (decoration,   4,  4),
    }


# ---------------------------------------------------------------------------
# District pools
# ---------------------------------------------------------------------------

DISTRICT_POOLS: dict[str, dict[str, float]] = {
    "residential": {
        "cottage":      0.35,
        "tower_house":  0.15,
        "blacksmith":   0.20,
        "clock_tower":  0.12,
        "tavern":       0.13,
        "farm":         0.05,
    },
    "farming": {
        "farm":         0.85,
        "market_stall": 0.15,
    },
    "fishing": {
        "dock":         0.50,
        "cottage":      0.30,
        "clock_tower":  0.15,
        "market_stall": 0.05,
    },
    "forest": {
        "tavern":       0.40,
        "tower_house":  0.35,
        "cottage":      0.25,
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

    Rotation is handled entirely inside build() — grammar builders
    never receive a rotation argument.
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        config: SettlementConfig,
        palette: PaletteSystem,
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

    def effective_footprint(self, plot: Plot, template_key: str) -> tuple[int, int]:
        """
        Return the (w, d) the selected builder will actually occupy.

        For house-grammar templates the grammar clamps build dimensions to
        7–11 (odd), so the effective footprint can be smaller than the plot.
        For all other builders the full plot dimensions are used.
        """
        if template_key in ("cottage", "tower_house"):
            from structures.house.house_grammar import HouseGrammar
            return HouseGrammar.effective_footprint(
                plot.width, plot.depth, facing_to_rotation(plot.facing)
            )
        return plot.width, plot.depth

    def build(self, plot: Plot, template_key: str) -> BlockBuffer | None:
        """
        Execute the selected template on the plot. Returns a BlockBuffer or
        None on failure.

        Rotation is applied here, after the grammar returns, using
        rotate_buffer() from core.buffer_transform. The grammar itself
        always builds axis-aligned.
        """
        entry = self._registry.get(template_key)
        if entry is None:
            logger.warning("Unknown template key '%s' — skipping.", template_key)
            return None

        builder, _, _ = entry
        try:
            buf = builder(plot, self.palette)
        except Exception:
            logger.error(
                "Builder '%s' failed on plot (%d,%d) size %dx%d.",
                template_key, plot.x, plot.z, plot.width, plot.depth,
                exc_info=True,
            )
            return None

        rotation = facing_to_rotation(plot.facing)
        if rotation != 0:
            # Use the effective footprint dimensions (post-clamping) so the
            # rotation pivot matches what the grammar actually built.
            w, d = self.effective_footprint(plot, template_key)
            buf  = rotate_buffer(buf, plot.x, plot.z, w, d, rotation)

        return buf

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
        keys   = list(pool.keys())
        total  = sum(pool.values())
        r      = random.random() * total
        cumulative = 0.0
        for key in keys:
            cumulative += pool[key]
            if r <= cumulative:
                return key
        return keys[-1]