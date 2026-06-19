"""
Logic Orchestrator: Floor Selection
Determines which grammar style to apply based on geometry and role.
"""
from __future__ import annotations
from structures.grammar.floor_grammar import rule_floor
from structures.base.build_context import BuildContext

def build_floor(
    ctx: BuildContext, 
    x: int, y: int, z: int, 
    w: int, d: int, 
    structure_role: str = "cottage"
) -> None:
    """
    Decides the floor pattern.
    Note: To hide the floor from the outside, the caller should 
    ideally inset the coordinates (x+1, z+1, w-2, d-2).
    """
    
    # 1. GEOMETRY & ROLE LOGIC
    if structure_role == "bridge":
        # Bridges look best with simple planks (plain)
        style = "plain"

    elif structure_role == "tower":
        # Towers feel more grand with a border
        style = "bordered"

    elif structure_role == "annex":
        # Social areas get high-detail patterns
        style = "parquet"

    elif w >= 7 and d >= 7:
        # Large rooms get a focal point
        style = "radial"

    elif (w + d) % 2 == 0:
        # Fallback for medium rooms
        style = "checker"

    else:
        # Small or odd-shaped rooms
        style = "rug"

    # 2. DISPATCH TO GRAMMAR
    rule_floor(ctx, x, y, z, w, d, style=style)