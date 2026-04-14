"""
Belfry Orchestrator
Maps structure roles to belfry designs.
"""
from __future__ import annotations
from structures.grammar.belfry_grammar import rule_belfry
from structures.base.build_context import BuildContext

def build_belfry(
    ctx: BuildContext, 
    x: int, y: int, z: int, 
    w: int, d: int, 
    h: int = 4,
    structure_role: str = "tower"
) -> None:
    """
    Selects the belfry design based on role.
    """
    # 1. STYLE SELECTION
    if structure_role == "watchtower":
        style = "arched" 
    else:
        style = "arched"

    # 2. DELEGATE
    rule_belfry(ctx, x, y, z, w, d, h=h, style=style)