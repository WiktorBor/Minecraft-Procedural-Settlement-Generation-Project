from __future__ import annotations
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.grammar.tavern_grammar import rule_tavern

def build_tavern(ctx: BuildContext, plot: Plot) -> None:
    """
    Orchestrates the Tavern complex.
    Ensures minimum space requirements and calculates component widths.
    """
    # Minimum requirements for a functional complex
    MIN_W, MIN_D = 19, 8
    
    if plot.width < MIN_W or plot.depth < MIN_D:
        return # Too small to build a full tavern

    # Component width calculation
    tw = 5 # Fixed Tower width
    bw = max(7, int(plot.width * 0.25)) # Bridge width
    cw = plot.width - tw - bw # Annex (Cottage) width
    
    # Standardize depth to be odd for roof symmetry
    d = plot.depth if plot.depth % 2 != 0 else plot.depth - 1
    
    rule_tavern(ctx, plot.x, plot.y, plot.z, tw, bw, cw, d)

    return ctx.buffer