from structures.base.build_context import BuildContext
from world_interface.block_buffer import BlockBuffer
from data.settlement_entities import Plot
from structures.grammar.tower_grammar import rule_tower

def build_tower(
    ctx: BuildContext, 
    plot: Plot, 
    tower_height: int = 12,
    structure_role: str = "fortification"
) -> BlockBuffer:
    """
    ORCHESTRATOR: Tower
    Standardized entry point for building a tower.
    Handles buffer creation and palette context.
    """
    
    # Pre-processing: If it's a fortification, ensure materials are stone-heavy
    # This keeps the grammar clean of specific block IDs.
    if structure_role == "fortification":
        stone_pal = dict(ctx.palette)
        found_mat = ctx.palette.get("foundation", "minecraft:stone_bricks")
        stone_pal.update({
            "wall": found_mat,
            "floor": found_mat,
            "accent": ctx.palette.get("accent_beam", "minecraft:stripped_dark_oak_log")
        })
    elif structure_role == "clock_tower":
        clock_pal = dict(ctx.palette)
        clock_pal.update({
            "wall": ctx.palette.get("clock_face", "minecraft:white_concrete"),
            "accent": ctx.palette.get("clock_hands", "minecraft:black_concrete")
        })
    
    # Execute the Grammar
    rule_tower(ctx, plot.x, plot.y, plot.z, plot.width, tower_height, plot.depth, structure_role=structure_role)
    
    return ctx.buffer