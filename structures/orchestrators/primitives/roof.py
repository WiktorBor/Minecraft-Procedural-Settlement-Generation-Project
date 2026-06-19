"""
Orchestrator: Roof Manager
Translates building 'intent' into grammar rules.
"""
from __future__ import annotations
from structures.grammar.roof_grammar import rule_roof
from structures.base.build_context import BuildContext

def build_roof(
    ctx: BuildContext, 
    x: int, y: int, z: int, 
    w: int, h: int, d: int, 
    structure_role: str | str = "cottage",
    connector_side: str | None = None
) -> None:
    """
    Decides roof style and orientation based on the part of the building.
    
    Args:
        structure_role: 'tower', 'bridge', 'annex', 'main', blacksmith, cottage
        connector_side: If this part connects to another (e.g., 'west' for the bridge side)
    """
    # 1. SELECT STYLE BASED ON ROLE
    if structure_role == "fortification":
        style = "pyramid"
        arm_side = None
    elif structure_role == "spire":
        style = "spire"
        arm_side = None
    elif structure_role == "bridge":
        style = "gabled"
        arm_side = None 
    elif structure_role == "annex":
        style = "cross" if connector_side else "gabled"
        arm_side = connector_side # e.g., "west"
    else:
        if w * d >= 90:
            style = "cross"
            arm_side = None
        else:
            style = "gabled"
            arm_side = None

    # 2. SELECT RIDGE ORIENTATION
    # Usually, ridges run along the longer axis, unless forced by a connector.
    orientation = "x" if w >= d else "z"

    # 3. CALL THE GRAMMAR
    rule_roof(
        ctx, x, y, z, w, h, d, 
        style=style, 
        orientation=arm_side or orientation
    )