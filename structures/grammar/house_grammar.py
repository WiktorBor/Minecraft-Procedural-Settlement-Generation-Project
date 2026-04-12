from structures.orchestrators.primitives.wall import build_wall
from structures.orchestrators.primitives.floor import build_floor
from structures.orchestrators.primitives.roof import build_roof
from structures.orchestrators.primitives.door import build_door
from structures.orchestrators.primitives.window import build_windows
from structures.orchestrators.primitives.stairs import build_stairs
from structures.orchestrators.primitives.ceiling import build_ceiling
from structures.base.build_context import BuildContext

def rule_house(
    ctx: BuildContext, 
    x: int, y: int, z: int, 
    w: int, d: int, 
    bridge_side: str = None,
    structure_role: str = "house",
    wall_h: int = 7
) -> None:
    """
    Grammar rule houses.
    """

    actual_wall_h = 5 if structure_role == "cottage" else wall_h

    # 1. Main Structure
    build_wall(ctx, x, y, z, w, actual_wall_h, d, structure_role=structure_role)
    build_floor(ctx, x + 1, y, z + 1, w - 2, d - 2, structure_role=structure_role)
    
    # 2. Openings
    door_side = build_door(ctx, x, y + 1, z, w, d, connector_side=bridge_side, structure_role=structure_role)
    build_windows(ctx, x, y, z, w, d, bridge_side=bridge_side, door_side=door_side, structure_role=structure_role)
    
    # 3. Verticality & Roof
    ceiling_y = y + actual_wall_h
    build_ceiling(ctx, x, ceiling_y, z, w, d, structure_role=structure_role)
    
    # Stairs logic using the storey height
    # build_stairs(ctx, x, y + 1, z, w, d, height=actual_wall_h-5, structure_role=structure_role, exit_facing=bridge_side)
    
    # 4. Roof with connector orientation
    build_roof(ctx, x, y, z, w, actual_wall_h, d, structure_role=structure_role, connector_side=bridge_side)