from structures.grammar.door_grammar import rule_door
from structures.base.build_context import BuildContext

from typing import Optional

def build_door(
        ctx: BuildContext, 
        x: int, y: int, z: int, 
        w: int, d: int, connector_side: Optional[str], 
        structure_role: str) -> str:
    """
    Places doors only on walls NOT occupied by the bridge.
    """
    # 1. Determine which walls are available (Not the bridge side)
    all_sides = ["north", "south", "east", "west"]
    available_sides = [s for s in all_sides if s != connector_side]
    
    # 2. Pick a 'Front' side (usually the one opposite the bridge or a specific side)
    # For this logic, let's put a door on the side adjacent to the bridge
    # so the player walks 'around' the bridge to enter.
    door_side = available_sides[0] 
    
    mid_x = x + (w // 2)
    mid_z = z + (d // 2)
    style = "arched" if structure_role == "annex" else "simple"
    
    # 3. Place the door on the chosen available wall
    if door_side == "north":
        rule_door(ctx, mid_x, y, z, style, facing="south")
    elif door_side == "south":
        rule_door(ctx, mid_x, y, z + d - 1, style, facing="north")
    elif door_side == "west":
        rule_door(ctx, x, y, mid_z, style, facing="east")
    elif door_side == "east":
        rule_door(ctx, x + w - 1, y, mid_z, style, facing="west")
    
    return door_side