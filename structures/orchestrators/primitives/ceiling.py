from structures.grammar.ceiling_grammar import rule_ceiling
from structures.base.build_context import BuildContext

def build_ceiling(
        ctx: BuildContext, 
        x: int, y: int, z: int, w: int, d: int, 
        structure_role: str) -> None:
    """
    Fills the top of the room (usually at y + height - 1).
    """
    # Ceilings are usually 1 block below the actual roof start
    ceil_y = y 
    
    # We fill the interior (w-2, d-2) to avoid overlapping the walls
    inner_x = x + 1
    inner_z = z + 1
    inner_w = w - 2
    inner_d = d - 2

    # Choose style based on role
    if structure_role == "main":
        style = "beams"  # Tavern vibe
    elif structure_role == "annex":
        style = "coffered" # Fancy kitchen/bedroom vibe
    else:
        style = "flat"

    # Fill the area by calling the grammar for each row
    # We "span" the ceiling across the shortest axis for beams
    if inner_w <= inner_d:
        for bz in range(inner_d):
            rule_ceiling(ctx, inner_x, ceil_y, inner_z + bz, 
                         style=style, facing="north", length=inner_w)
    else:
        for bx in range(inner_w):
            rule_ceiling(ctx, inner_x + bx, ceil_y, inner_z, 
                         style=style, facing="west", length=inner_d)