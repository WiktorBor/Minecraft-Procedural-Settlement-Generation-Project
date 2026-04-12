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
        return

    # 2. Random Plot Shrinkage (as in original builder)
    w = max(5, plot.width - random.choice([0, 2]))
    d = max(5, plot.depth - random.choice([0, 2]))

    # 3. Call Grammar
    rule_farm(ctx, plot.x, plot.y, plot.z, w, d)