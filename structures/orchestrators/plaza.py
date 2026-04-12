from structures.base.build_context import BuildContext
from structures.grammar.plaza_grammar import rule_plaza_floor, rule_grand_spire, rule_small_fountain
from data.settlement_entities import Plot
from gdpc import Block

def build_square_centre(ctx: BuildContext, plot: Plot):
    """
    Orchestrator for the stone plaza centerpiece.
    Decides between Small and Grand styles based on plot size.
    """
    cx = plot.x + plot.width // 2
    cy = plot.y
    cz = plot.z + plot.depth // 2
    radius = min(plot.width, plot.depth) // 2

    if radius < 3:
        # Simple fallback paving
        for ix in range(plot.x, plot.x + plot.width):
            for iz in range(plot.z, plot.z + plot.depth):
                ctx.place_block((ix, cy, iz), Block("minecraft:stone_bricks"))
        return

    # Determine Style
    if radius >= 8:
        effective_radius = min(radius, 25)
        clear_h = 35
        # 1. Floor
        rule_plaza_floor(ctx, cx, cy, cz, effective_radius, clear_h)
        # 2. Spire
        rule_grand_spire(ctx, cx, cy, cz, effective_radius)
    else:
        # 1. Floor
        rule_plaza_floor(ctx, cx, cy, cz, radius, 15)
        # 2. Small Fountain
        rule_small_fountain(ctx, cx, cy, cz, radius)

    # 3. Foundation (always build downward to prevent floating)
    _fill_plaza_foundation(ctx, cx, cy, cz, radius)

def _fill_plaza_foundation(ctx: BuildContext, cx: int, cy: int, cz: int, radius: int):
    for dx in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            if dx**2 + dz**2 <= radius**2:
                for dy in range(1, 10):
                    ctx.place_block((cx + dx, cy - dy, cz + dz), Block("minecraft:stone"))