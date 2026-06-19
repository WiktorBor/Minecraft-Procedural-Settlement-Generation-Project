from structures.base.build_context import BuildContext
from structures.orchestrators.tower import build_tower
from structures.house.house import build_house_settlement
from data.settlement_entities import Plot
from gdpc import Block

def build_spire_tower(ctx: BuildContext, plot: Plot) -> None:
    # Partition
    tw, td = 5, 5
    hx, hw = plot.x + tw, plot.width - tw

    # Build Tower (Base + Spire Roof)
    build_tower(
        ctx, 
        plot=Plot(x=plot.x, y=plot.y, z=plot.z, width=tw, depth=td), 
        structure_role="spire")
    
    # Build House (Annex)
    house_plot = Plot(x=hx, y=plot.y, z=plot.z, width=hw, depth=plot.depth)
    build_house_settlement(ctx, house_plot)
    
    # Punch through the connection
    pass_z = plot.z + td // 2
    ctx.place_block((hx - 1, plot.y + 1, pass_z), Block("minecraft:air"))
    ctx.place_block((hx - 1, plot.y + 2, pass_z), Block("minecraft:air"))

    ctx.place_block((hx, plot.y + 1, pass_z), Block("minecraft:air"))
    ctx.place_block((hx, plot.y + 2, pass_z), Block("minecraft:air"))
    return ctx.buffer
