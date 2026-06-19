"""
Wall Orchestrator: Design Selector
Maps structure roles to wall grammar styles.
"""
from __future__ import annotations
from structures.grammar.wall_grammar import rule_wall
from structures.base.build_context import BuildContext

def build_wall(
    ctx: BuildContext, 
    x: int, y: int, z: int, 
    w: int, h: int, d: int, 
    structure_role: str = "cottage",
    skip_sides: set[str] = set()
) -> None:
    """
    Decides the wall design pattern based on the role of the building.
    """
    # 1. SELECT STYLE BASED ON ROLE
    if structure_role == "tower":
        # Towers are defensive: Solid stone
        style = "plain" 
        
    elif structure_role == "bridge":
        # Bridge walls are usually stone/foundation to match the arches
        style = "fenced" 
        
    elif structure_role == "annex":
        # Annexes are cozy/medieval: Timber frame
        style = "timber"
        
    elif structure_role == "basement":
        # Underground or low levels
        style = "foundation"
        
    else:
        # Default house style
        style = "timber" if (w > 5 and d > 5) else "plain"

    # 2. DELEGATE TO GRAMMAR
    # The 'rule_wall' muscle now takes the design choice and executes it.
    rule_wall(ctx, x, y, z, w, h, d, style=style, skip_sides=skip_sides)