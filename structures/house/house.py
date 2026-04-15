import logging
import random
from dataclasses import replace

from structures.base.build_context import BuildContext
from structures.house.house_grammar import rule_house
from palette.palette_system import PaletteSystem
from data.settlement_entities import Plot
from structures.house.house_scorer import HouseScorer, HouseParams
from structures.house.house_ngram_scorer import HouseNgramScorer, BlockSequenceRecorder

logger = logging.getLogger(__name__)

# Load the 9-feature model
SCORER = HouseScorer.load("models/house_scorer.pkl")

# Load the n-gram perplexity model (falls back gracefully if not trained yet)
NGRAM_SCORER = HouseNgramScorer.load("models/house_ngram.pkl")

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

    # Probe pass: record block sequence to compute perplexity
    recorder = BlockSequenceRecorder()
    probe_ctx = replace(ctx, buffer=recorder)
    rule_house(probe_ctx, plot.x, plot.y, plot.z, best_params.w, best_params.d, params=best_params)
    sequence = recorder.finish()

    if NGRAM_SCORER.model is not None:
        perplexity = NGRAM_SCORER.model.perplexity(sequence)
        ngram_score = NGRAM_SCORER.perplexity_to_score(perplexity)
        logger.info(
            "House built at (%d, %d) | rf_score=%.3f | perplexity=%.2f | ngram_score=%.3f",
            plot.x, plot.z, best_score, perplexity, ngram_score,
        )
    else:
        logger.info(
            "House built at (%d, %d) | rf_score=%.3f | perplexity=n/a (ngram model not trained)",
            plot.x, plot.z, best_score,
        )

    # Build the winner directly using the consolidated rule_house
    rule_house(
        ctx,
        plot.x, plot.y, plot.z,
        best_params.w, best_params.d,
        params=best_params
    )

    return (plot.x, plot.z, plot.x + plot.width - 1, plot.z + plot.depth - 1)