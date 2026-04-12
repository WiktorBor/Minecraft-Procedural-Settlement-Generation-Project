from __future__ import annotations
import random
from data.settlement_entities import Plot
from structures.base.build_context import BuildContext
from structures.grammar.decoration_grammar import rule_well, rule_fountain

def build_decoration(ctx: BuildContext, plot: Plot) -> None:
    """
    Orchestrates decoration placement. 
    Selects a random decoration type appropriate for the plot dimensions.
    """
    # Calculate Center
    cx = plot.x + plot.width // 2
    cz = plot.z + plot.depth // 2
    
    # Decisions based on original builder logic
    # Fountains are 5x5, Wells are 3x3.
    choices = []
    if plot.width >= 3 and plot.depth >= 3:
        choices.append("well")
    if plot.width >= 5 and plot.depth >= 5:
        choices.append("fountain")

    if not choices:
        return

    choice = random.choice(choices)
    
    if choice == "well":
        # Wells are 3x3, centered in plot
        rule_well(ctx, cx - 1, plot.y, cz - 1)
    else:
        # Fountains are 5x5, centered in plot
        rule_fountain(ctx, cx, plot.y, cz)