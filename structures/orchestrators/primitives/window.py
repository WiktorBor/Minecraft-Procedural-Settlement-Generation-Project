from structures.grammar.window_grammar import rule_window
from structures.base.build_context import BuildContext
import random
from typing import Optional

def build_windows(
        ctx: BuildContext, 
        x: int, y: int, z: int, 
        w: int, d: int, 
        bridge_side: Optional[str] = None, 
        door_side: Optional[str] = None, 
        structure_role: str = "house"):
    """
    Standalone orchestrator for structures that need windows.
    """
    win_y = y + 2
    
    faces = [
        ("north", x + 1, z,         "south", w - 2),
        ("south", x + 1, z + d - 1, "north", w - 2),
        ("west",  x,         z + 1, "east",  d - 2),
        ("east",  x + w - 1, z + 1, "west",  d - 2)
    ]

    for side_name, sx, sz, face_dir, wall_len in faces:
        # Skip the bridge side
        if side_name == bridge_side:
            continue 
            
        style = "standard" if structure_role == "annex" else random.choice(["arched", "slit"])
        mid = wall_len // 2

        if side_name == door_side:
            # If there's a door, place windows around it
            for i in range(0, mid - 1 , 2):
                rule_window(ctx, sx, win_y, sz, style, face_dir, offset=i)

            for i in range(mid + 2, wall_len, 2):
                rule_window(ctx, sx, win_y, sz, style, face_dir, offset=i)
        else:
            # Call the grammar rule for each valid offset in the wall
            for i in range(0, wall_len, 2):
                rule_window(ctx, sx, win_y, sz, style=style, facing=face_dir, offset=i)