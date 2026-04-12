from structures.orchestrators.primitives.floor import build_floor
from structures.orchestrators.primitives.wall import build_wall
from structures.orchestrators.primitives.ceiling import build_ceiling
from structures.orchestrators.primitives.roof import build_roof
from structures.orchestrators.primitives.door import build_door
from structures.orchestrators.primitives.window import build_windows
from structures.orchestrators.primitives.stairs import build_stairs
from structures.grammar.belfry_grammar import rule_belfry

from structures.base.build_context import BuildContext
from gdpc import Block

def rule_tower(
        ctx: BuildContext, 
        x: int, y: int, z: int, 
        w: int, h: int, d: int,
        connector_side: str = None,
        structure_role: str = "tower") -> None:
    """
    Standard Grammar Signature.
    Assembles a tower by delegating to specialized orchestrators.
    """
    
    # 1. Base Layer (Foundation & Ground Floor)
    build_floor(ctx, x, y, z, w, d, structure_role=structure_role)
    
    # 2. Main Shaft (Stone Walls)
    # We build the walls from ground level up to the height (h)
    build_wall(ctx, x, y, z, w, h, d, structure_role=structure_role)

    # 3. Conditional Opennings: Doors and Windows
    if structure_role == "tower_house":
        build_door(ctx, x, y + 1, z, w, d, connector_side = connector_side, structure_role=structure_role)
        
        # Windows: We can add them at multiple levels
        # Level 1 (Ground)
        build_windows(ctx, x, y + 2, z, w, d, structure_role=structure_role)
        # Level 2 (Mid-shaft)
        if h > 6:
            build_windows(ctx, x, y + h - 4, z, w, d, structure_role=structure_role)
    elif structure_role == "tower":
        build_windows(ctx, x, y + 2, z, w, d, structure_role=structure_role)
    elif structure_role == "clock_tower":
        _add_clock_faces(ctx, x, y + h - 3, z, w, d)
    
    # 4. Intermediate Floor / Ceiling
    # This separates the stone base from the belfry
    base_top_y = y + h
    build_ceiling(ctx, x - 1, base_top_y, z - 1, w + 2, d + 2, structure_role=structure_role)

    # 5. Transition "Belt"
    # A decorative 1-block ring, often made of logs
    belt_y = base_top_y + 1
    build_wall(ctx, x, belt_y, z, w, 1, d, structure_role="accent")


    # 5. The Belfry (Open-air arches)
    belfry_y = belt_y + 1
    belfry_h = 4
    # Note: You can create a build_belfry orchestrator following your pattern!
    rule_belfry(ctx, x, belfry_y, z, w, d, belfry_h, style="arched")

    # 6. The Ceiling below the Roof
    ceili_base_y = belfry_y + belfry_h
    build_ceiling(ctx, x, ceili_base_y, z, w, d, structure_role=structure_role)
    
    # 7. The Roof (Spire)
    spire_y = y + belfry_h + 2
    build_roof(ctx, x, spire_y , z, w, h, d, structure_role=structure_role, connector_side=connector_side)

def _add_clock_faces(ctx: BuildContext, x: int, y: int, z: int, w: int, d: int) -> None:
    """
    Adds a 3x3 bone-block clock face with a gold center on all four sides.
    """

    mat_clock_face = ctx.palette.get("clock_face", "minecraft:bone_block")
    mat_accent = ctx.palette.get("clock_hands", "minecraft:gold_block")

    # Calculate the center of the tower shaft
    cx = x + w // 2
    cz = z + d // 2
    
    # Radius from center to the wall face
    rx = w // 2
    rz = d // 2

    # fdx/fdz represent the face direction (North, South, East, West)
    for fdx, fdz in [(0, -rz), (0, rz), (rx, 0), (-rx, 0)]:
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                # Calculate placement
                # If we are on a Z-face (North/South), dx shifts the X
                # If we are on an X-face (East/West), dx shifts the Z
                px = cx + (dx if fdz != 0 else fdx)
                py = y + dy
                pz = cz + (fdz if fdz != 0 else dx)
                
                ctx.place_block((px, py, pz), Block(mat_clock_face))
        
        # Place the gold center piece exactly in the middle of the 3x3
        ctx.place_block((cx + fdx, y, cz + fdz), Block(mat_accent))
