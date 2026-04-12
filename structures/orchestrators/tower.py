from structures.base.build_context import BuildContext
from world_interface.block_buffer import BlockBuffer
from structures.grammar.tower_grammar import rule_tower

def build_tower(
    palette, 
    x: int, y: int, z: int, 
    w: int = 5, h: int = 10, d: int = 5, 
    structure_role: str = "fortification"
) -> BlockBuffer:
    """
    ORCHESTRATOR: Tower
    Standardized entry point for building a tower.
    Handles buffer creation and palette context.
    """
    buffer = BlockBuffer()
    
    # Pre-processing: If it's a fortification, ensure materials are stone-heavy
    # This keeps the grammar clean of specific block IDs.
    if structure_role == "fortification":
        stone_pal = dict(palette)
        found_mat = palette.get("foundation", "minecraft:stone_bricks")
        stone_pal.update({
            "wall": found_mat,
            "floor": found_mat,
            "accent": palette.get("accent_beam", "minecraft:stripped_dark_oak_log")
        })
        ctx = BuildContext(buffer, stone_pal)
    elif structure_role == "clock_tower":
        clock_pal = dict(palette)
        clock_pal.update({
            "wall": palette.get("clock_face", "minecraft:white_concrete"),
            "accent": palette.get("clock_hands", "minecraft:black_concrete")
        })
        ctx = BuildContext(buffer, clock_pal)
    else:
        ctx = BuildContext(buffer, palette)

    # Execute the Grammar
    rule_tower(ctx, x, y, z, w, h, d, structure_role=structure_role)
    
    return buffer