from __future__ import annotations
from structures.base.build_context import BuildContext
from structures.orchestrators.primitives.bridge import build_bridge
from structures.house.house import build_house_settlement
from structures.orchestrators.tower import build_tower
from data.settlement_entities import Plot

def rule_tavern(ctx: BuildContext, x, y, z, tw, bw, cw, d):
    """
    The assembly rule for the Tavern:
    [ Tower (tw) ] --- [ Bridge (bw) ] --- [ Annex (cw) ]
    """
    bridge_y = y + 3
    t_offset_z = (d - tw) // 2

    # 1. Modular Bridge (Connector Style)
    # This uses your new symmetrical pillar logic and 3-block interior width
    bridge_plot = Plot(x=x + tw, y=bridge_y, z=z, width=bw, depth=tw)
    build_bridge(
        ctx, 
        bridge_plot, 
        structure_role="connector", 
        span_axis="x"
    )

    # 2. Modular Tower
    # We build a tower with a height that allows the bridge to connect properly
    tower_height = 9 
    build_tower(ctx,
                Plot(x=x, y=y, z=z, width=tw, depth=tw),
                tower_height)

    # 3. Modular Annex (Cottage)
    # Uses rule_house to ensure the annex looks like other settlement buildings
    # bridge_side="west" tells the house to place the door/opening where the bridge lands
    build_house_settlement(
        ctx, 
        Plot(x = x + tw + bw, y=y, z=z - t_offset_z, width=cw, depth=d),
        bridge_side="west", 
        structure_role="annex",
    )