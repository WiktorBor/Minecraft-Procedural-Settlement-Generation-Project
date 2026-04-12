from structures.base.build_context import BuildContext
from structures.grammar.house_grammar import rule_house
from palette.palette_system import PaletteSystem
from data.settlement_entities import Plot

def build_house_settlement(
    ctx: BuildContext,
    plot: Plot,
    palette: PaletteSystem,
    bridge_side: str = None,
    structure_role: str = "house",
    wall_h: int = 6
) -> tuple[int, int, int, int]:
    """
    Orchestrator for houses. 
    Focuses on terrain placement and grammar delegation.
    """
    # 1. Determine ground height at plot center
    cx = plot.x + plot.width // 2
    cz = plot.z + plot.depth // 2
    gy = plot.y
    
    # 2. Create an axis-aligned context
    # We ignore plot.rotation here because the final buffer will be rotated
    house_ctx = BuildContext(
        ctx.buffer, 
        palette, 
    )

    # 3. Delegate to Grammar (No Primitives)
    # 'bridge_side' is passed as a fixed orientation relative to the tower/bridge
    rule_house(
        house_ctx, 
        plot.x, gy, plot.z, 
        plot.width, plot.depth, 
        bridge_side=bridge_side, 
        structure_role=structure_role,
        wall_h=wall_h
    )

    # 4. Return bounds for collision/fortification logic
    return (plot.x, plot.z, plot.x + plot.width - 1, plot.z + plot.depth - 1)