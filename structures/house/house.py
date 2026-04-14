from structures.base.build_context import BuildContext
from structures.house.house_grammar import rule_house
from palette.palette_system import PaletteSystem
from data.settlement_entities import Plot
from structures.house.house_scorer import HouseScorer, HouseParams
import random

# Load the 9-feature model
SCORER = HouseScorer.load("models/house_scorer.pkl")

def build_house_settlement(
    ctx: BuildContext,
    plot: Plot,
    bridge_side: str = None,
    structure_role: str = "house"
) -> tuple[int, int, int, int]:
    """
    Orchestrator: Uses a 9-feature Random Forest to pick the best house design.
    """
    best_score = -1
    best_params = None

    for _ in range(5):
        test_wall_h = random.randint(4, 7)
        test_roof = random.choice(["gabled", "cross"])
        
        # Define 9 features matching house_labels.csv and train_scorer.py
        params = HouseParams(
            w=plot.width,
            d=plot.depth,
            wall_h=test_wall_h,
            structure_role=structure_role,
            roof_type=test_roof,
            has_upper=(test_wall_h > 5),
            has_chimney=random.random() > 0.7,
            has_porch=random.random() > 0.8,
            bridge_side=bridge_side
        )

        score = SCORER.score(params)

        if score > best_score:
            best_score = score
            best_params = params

    # Build the winner directly using the consolidated rule_house
    rule_house(
        ctx, 
        plot.x, plot.y, plot.z, 
        best_params.w, best_params.d, 
        params=best_params 
    )

    return (plot.x, plot.z, plot.x + plot.width - 1, plot.z + plot.depth - 1)