from structures.base.build_context import BuildContext
from structures.house.house import build_house_settlement
from structures.orchestrators.primitives.roof import build_roof
from structures.grammar.blacksmith_grammar import rule_forge_work_area, rule_chimney
from data.settlement_entities import Plot
from gdpc import Block

def build_blacksmith(ctx: BuildContext, plot: Plot):
    """
    Composed Blacksmith: 
    Uses the House Orchestrator for the living wing and 
    custom grammar for the forge/chimney.
    """
    # 1. Spatial Partitioning
    # Split the width: 60% House, 1 block Chimney, rest is Forge
    left_w = max(5, (plot.width * 6) // 10)
    if left_w % 2 == 0: left_w -= 1
    
    chim_x = plot.x + left_w
    right_x = chim_x + 1
    right_w = plot.width - left_w - 1
    
    # 2. Build the Living Wing (USING EXISTING HOUSE MODULE)
    # We create a sub-plot and pass it to your existing house orchestrator
    house_plot = Plot(x=plot.x, y=plot.y, z=plot.z, width=left_w, depth=plot.depth)
    build_house_settlement(ctx, house_plot, structure_role="blacksmith")

    # 3. Build the Forge Work Area (Custom Grammar)
    # The forge is simpler than a house, so we use a specific grammar rule
    forge_d = (plot.depth * 4) // 10
    rule_forge_work_area(ctx, right_x, plot.y, plot.z, right_w, plot.depth, 5, forge_d)

    # 4. Build the Chimney
    rule_chimney(ctx, chim_x, plot.y, plot.z + (plot.depth // 2), height=10)

    return ctx.buffer