from __future__ import annotations
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.grammar.tavern_grammar import rule_tavern

def build_tavern(ctx: BuildContext, plot: Plot) -> None:
    """
    Orchestrates the Tavern complex.
    Ensures minimum space requirements and calculates component widths.
    """

    tw = 5  # Fixed Tower

    # Bridge takes whatever is left
    bw = int(plot.width * 0.3)
    cw = plot.width - tw - bw
    
    # Standardize depth to be odd for roof symmetry
    d = plot.depth if plot.depth % 2 != 0 else plot.depth - 1
    
    rule_tavern(ctx, plot.x, plot.y, plot.z, tw, bw, cw, d)

    return ctx.buffer