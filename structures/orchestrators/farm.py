from __future__ import annotations
import random
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.grammar.farm_grammar import rule_farm

def build_farm(ctx: BuildContext, plot: Plot) -> None:
    """
    Orchestrates farm construction. 
    Handles plot shrinkage and min-size validation.
    """
    # 1. Dimension Validation: Minimum 5x5
    if plot.width < 5 or plot.depth < 5:
        return ctx.buffer

    # 3. Call Grammar
    rule_farm(ctx, plot.x, plot.y, plot.z, plot.width, plot.depth)

    return ctx.buffer