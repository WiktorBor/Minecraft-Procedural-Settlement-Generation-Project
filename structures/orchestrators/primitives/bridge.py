"""
Bridge Orchestrator: Design Selector
Connects high-level settlement roles to specific bridge grammars.
"""
from __future__ import annotations
from structures.grammar.bridge_grammar import rule_stone_arch_bridge, rule_connector_wing_bridge
from structures.base.build_context import BuildContext
from data.settlement_entities import Plot

def build_bridge(
    ctx: BuildContext, 
    plot: Plot, 
    structure_role: str = None,
    span_axis: str = "x"
) -> None:
    """
    Orchestrates bridge construction based on role.
    
    Roles:
    - 'infrastructure': Open stone bridge for rivers or roads.
    - 'connector': Enclosed wooden hallway bridge (Tavern-style) for building wings.
    """
    # Standardize dimensions from the Plot
    x, y, z = plot.x, plot.y, plot.z
    w, d = plot.width, plot.depth

    if structure_role == "connector":
        # Uses the complex Belfry-integrated logic
        rule_connector_wing_bridge(ctx, x, y, z, w, d, span_axis=span_axis)
    else:
        # Uses the heavy stone arch logic
        rule_stone_arch_bridge(ctx, x, y, z, w, d, span_axis=span_axis)