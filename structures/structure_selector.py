from __future__ import annotations
import logging
import random
from typing import Callable
from dataclasses import replace

from palette.palette_system import PaletteSystem
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.buffer_transform import facing_to_rotation, rotate_buffer
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)

def _make_ctx(pal: PaletteSystem) -> tuple[BuildContext, BlockBuffer]:
    buf = BlockBuffer()
    return BuildContext(buffer=buf, palette=pal), buf

def _build_registry() -> dict[str, tuple[Callable, int, int]]:
    """
    Registry of builder functions. 
    Note: Orchestrators called here should be cleaned of internal clamping.
    """
    def cottage(pl, pal):
        from structures.house.house import build_house_settlement
        ctx, buf = _make_ctx(pal)
        build_house_settlement(ctx, pl)
        return buf

    def blacksmith(pl, pal):
        from structures.orchestrators.blacksmith import build_blacksmith
        ctx, buf = _make_ctx(pal)
        build_blacksmith(ctx, pl)
        return buf

    def dock(pl, pal):
        from structures.orchestrators.dock import build_dock
        ctx, buf = _make_ctx(pal)
        build_dock(ctx, pl)
        return buf

    def market(pl, pal):
        from structures.orchestrators.market import build_market_stall
        ctx, buf = _make_ctx(pal)
        build_market_stall(ctx, pl)
        return buf

    def clock_tower(pl, pal):
        from structures.orchestrators.tower import build_tower
        ctx, buf = _make_ctx(pal)
        build_tower(ctx, pl, structure_role="clock_tower")
        return buf

    def tavern(pl, pal):
        from structures.orchestrators.tavern import build_tavern
        ctx, buf = _make_ctx(pal)
        build_tavern(ctx, pl)
        return buf

    def spire_tower(pl, pal):
        from structures.orchestrators.spire_tower import build_spire_tower
        ctx, buf = _make_ctx(pal)
        build_spire_tower(ctx, pl)
        return buf

    def plaza(pl, pal):
        from structures.orchestrators.plaza import build_square_centre
        ctx, buf = _make_ctx(pal)
        build_square_centre(ctx, pl)
        return buf

    def farm(pl, pal):
        from structures.orchestrators.farm import build_farm
        ctx, buf = _make_ctx(pal)
        build_farm(ctx, pl)
        return buf

    def decoration(pl, pal):
        from structures.orchestrators.primitives.decoration import build_decoration
        ctx, buf = _make_ctx(pal)
        build_decoration(ctx, pl)
        return buf
    
    return {
        "cottage":      (cottage,      7,  7),
        "spire_tower":  (spire_tower, 10,  6),
        "blacksmith":   (blacksmith,   9,  8),
        "plaza":        (plaza,       10, 10),
        "market":       (market,       5,  5),
        "clock_tower":  (clock_tower,  8,  8),
        "tavern":       (tavern,      19,  8),
        "farm":         (farm,         5,  5),
        "dock":         (dock,        14, 10),
        "decoration":   (decoration,   4,  4)
    }

# District pools configuration remains unchanged
DISTRICT_POOLS: dict[str, dict[str, float]] = {
    "residential": {"cottage": 0.35, "spire_tower": 0.15, "blacksmith": 0.20, "clock_tower": 0.12, "tavern": 0.13, "farm": 0.05},
    "farming":     {"farm": 0.60, "cottage": 0.15, "market": 0.25},
    "fishing":     {"clock_tower": 0.20, "cottage": 0.50, "market": 0.30},
    "forest":      {"tavern": 0.30, "spire_tower": 0.35, "cottage": 0.35},
}
FALLBACK_POOL: dict[str, float] = {"cottage": 0.40, "clock_tower": 0.40, "market": 0.20}

class StructureSelector:
    def __init__(self, analysis, config, palette, has_water=False):
        self.analysis = analysis
        self.config = config
        self.palette = palette
        self.has_water = has_water
        self._registry = _build_registry()
        
        # SINGLE SOURCE OF TRUTH for constraints
        self._constraints = {
            "cottage":      (7,  7,  11, 11),
            "spire_tower":  (10, 6,  14, 10),
            "blacksmith":   (9,  8,  13, 12),
            "clock_tower":  (5,  5,  8,  8),
            "tavern":       (13, 8,  19, 12),
            "farm":         (5,  5,  10, 10),
            "market":       (5,  5,  10, 10),
            "dock":         (14, 10, 20, 15),
            "tower":        (5,  5,  8,  8),
            "decoration":   (4,  4,  6,  6)
        }

    def select(self, plot: Plot) -> str | None:
        dtype = (plot.type or "residential").strip().lower()
        if dtype == "fishing" and not self.has_water:
            dtype = "residential"

        pool = DISTRICT_POOLS.get(dtype, FALLBACK_POOL)

        eligible_pool = {}
        for key, weight in pool.items():
            if key in self._constraints:
                min_w, min_d, _, _ = self._constraints[key]
                if plot.width >= min_w and plot.depth >= min_d:
                    eligible_pool[key] = weight

        if not eligible_pool:
            return None

        return self._weighted_choice(eligible_pool)

    def _weighted_choice(self, pool: dict[str, float]) -> str:
        keys = list(pool.keys())
        weights = list(pool.values())
        return random.choices(keys, weights=weights, k=1)[0]

    def effective_footprint(self, plot: Plot, template_key: str) -> tuple[int, int]:
        """Calculates exact dimensions. Orchestrators should NOT re-calculate these."""
        if template_key not in self._constraints:
            return plot.width, plot.depth
            
        min_w, min_d, max_w, max_d = self._constraints[template_key]
        
        # 1. Primary Clamp
        ew = max(min_w, min(max_w, plot.width))
        ed = max(min_d, min(max_d, plot.depth))
        
        # 2. Force Symmetry (Odd Numbers)
        if ew % 2 == 0: ew -= 1
        if ed % 2 == 0: ed -= 1
        
        # 3. Final safety check against original plot bounds
        return max(min_w, ew), max(min_d, ed)

    def build(self, plot: Plot, template_key: str) -> BlockBuffer | None:
        entry = self._registry.get(template_key)
        if not entry: return None
        builder, _, _ = entry

        # THE SINGLE CLAMP:
        ew, ed = self.effective_footprint(plot, template_key)
        
        # Force the orchestrator to build in the effective size, ignoring original plot scale
        clamped_world_plot = replace(plot, width=ew, depth=ed)

        buf = builder(clamped_world_plot, self.palette)

        if buf is None or len(buf) == 0:
            logger.warning(f"Builder for {template_key} returned empty buffer")
            return None
        
        # Rotation is applied based on the FIXED effective footprint
        rotation = facing_to_rotation(plot.facing)
        if rotation != 0:
            buf = rotate_buffer(buf, plot.x, plot.z, ew, ed, rotation)
            
        return buf