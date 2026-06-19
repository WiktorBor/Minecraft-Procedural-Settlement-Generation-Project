from structures.base.build_context import BuildContext
from structures.grammar.dock_grammar import rule_dock_deck, rule_dock_pillar, rule_dock_railings
from data.settlement_entities import Plot

def build_dock(ctx: BuildContext, plot: Plot):
    x, y, z = plot.x, plot.y, plot.z
    w, d = plot.width, plot.depth

    # 1. Spatial Partitioning
    main_d = (d * 3) // 5
    pier_d = d - main_d
    pier_w = w // 3
    if pier_w % 2 == 0: pier_w -= 1 
    pier_x = x + (w - pier_w) // 2

    # 2. Build Main Deck
    rule_dock_deck(ctx, x, y, z, w, main_d)
    _place_grid_pillars(ctx, x, y, z, w, main_d)
    # Leave 'south' open where the pier connects
    rule_dock_railings(ctx, x, y, z, w, main_d, open_sides=['south'])

    # 3. Build Finger Pier
    if pier_d >= 2:
        rule_dock_deck(ctx, pier_x, y, z + main_d, pier_w, pier_d)
        _place_grid_pillars(ctx, pier_x, y, z + main_d, pier_w, pier_d)
        # Leave 'north' open to connect to main deck
        rule_dock_railings(ctx, pier_x, y, z + main_d, pier_w, pier_d, open_sides=['north'])

    # 4. Lighting
    # Place lanterns on the corner bollards
    for lx, lz in [(x, z), (x + w - 1, z), (pier_x, z + d - 1), (pier_x + pier_w - 1, z + d - 1)]:
        ctx.place_light((lx, y + 2, lz), key="light", hanging=False)

    return ctx.buffer

def _place_grid_pillars(ctx, x, y, z, w, d, step=3):
    """Helper to place pillars on the corners and edges."""
    points = set()
    for dx in [0, w - 1]:
        for dz in range(0, d, step): points.add((x + dx, z + dz))
        points.add((x + dx, z + d - 1))
    for dz in [0, d - 1]:
        for dx in range(0, w, step): points.add((x + dx, z + dz))
        points.add((x + w - 1, z + dz))
        
    for px, pz in points:
        rule_dock_pillar(ctx, px, y, pz)