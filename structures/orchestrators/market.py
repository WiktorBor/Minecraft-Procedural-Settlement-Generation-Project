from structures.base.build_context import BuildContext
from structures.grammar.market_grammar import (
    rule_market_supports, rule_market_counter, rule_market_canopy
)
from data.settlement_entities import Plot
from gdpc import Block

def build_market_stall(ctx: BuildContext, plot: Plot):
    """
    Assembles a detailed market stall centered in the plot.
    """
    # 1. Scaling & Logic
    # Clamp size so it stays a 'stall' even in a large plot
    sw = min(plot.width, 7)
    sd = min(plot.depth, 5)
    if sw < 3 or sd < 3: return # Too small to build
    
    # Calculate local origin to center the stall in the plot
    sx = plot.x + (plot.width - sw) // 2
    sy = plot.y
    sz = plot.z + (plot.depth - sd) // 2
    sh = 3 # Height of the support beams

    # 2. Foundation
    _build_foundation(ctx, sx, sy, sz, sw, sd)

    # 3. Assemble Components
    rule_market_supports(ctx, sx, sy, sz, sw, sd, sh)
    rule_market_counter(ctx, sx, sy, sz, sw, sd)
    rule_market_canopy(ctx, sx, sy, sz, sw, sd, sh)

def _build_foundation(ctx, x, y, z, w, d):
    """Ensures a solid cobblestone base beneath the stall."""
    found = ctx.palette.get("foundation", "minecraft:cobblestone")
    for dx in range(w):
        for dz in range(d):
            # Fill 3 blocks down to be safe on uneven terrain
            for dy in range(0, 4):
                ctx.place_block((x + dx, y - dy, z + dz), Block(found))
