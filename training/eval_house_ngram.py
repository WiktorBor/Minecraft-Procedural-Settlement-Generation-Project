"""
Offline training and evaluation script for the house n-gram scorer.

What this script does
---------------------
1. Runs HouseGrammar N times on synthetic plots, using BlockSequenceRecorder
   to capture the block-ID sequence each build emits.
2. Generates the first half as good houses and the second half as explicitly
   bad houses (via force_bad=True) so the two groups are structurally distinct.
3. Trains a NgramLanguageModel on the good sequences only.
4. Reports perplexity for three groups:
       Good houses  (upper storey, chimney, porch)
       Bad houses   (no upper storey, no chimney, cross roof on small plot)
       Random       (sequences shuffled — destroys all spatial structure)
5. Saves the trained model to models/house_ngram.pkl.

Expected result
---------------
    Good perplexity  <  Bad perplexity  <  Random perplexity

This is your reportable metric.  Cite it as:

    "Our grammar generates houses with mean block-sequence perplexity of P1
     (n-gram order 3, Laplace α=0.1), compared to P2 for parameter sets
     rejected by the aesthetic scorer and P3 for a shuffled random baseline,
     demonstrating that the grammar produces structurally coherent block
     transitions."

Usage
-----
    python3 -m structures.house.eval_house_ngram \
        [--n-houses 300]       \
        [--ngram-order 3]      \
        [--alpha 0.1]          \
        [--blend-weight 0.25]  \
        [--model-out models/house_ngram.pkl] \
        [--dry-run]

    Pass --dry-run to use NullEditor (no Minecraft connection required).
"""
from __future__ import annotations

import argparse
import logging
import random
import statistics
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NullEditor — lets the script run without a live Minecraft connection
# ---------------------------------------------------------------------------

class NullEditor:
    """
    Minimal Editor stand-in for dry-run mode.

    Accepts placeBlock calls and discards them. All other attribute access
    raises AttributeError so real Editor-only code surfaces bugs early.
    """

    def placeBlock(self, position, block) -> None:
        pass  # intentionally discard

    def __getattr__(self, name: str):
        raise AttributeError(
            f"NullEditor does not support '{name}' — use a real Editor for live builds."
        )


# ---------------------------------------------------------------------------
# Synthetic plot factory
# ---------------------------------------------------------------------------

def _random_plot(min_w: int = 5, max_w: int = 12):
    """
    Return a lightweight Plot-like object with random dimensions.

    Avoids importing the full data layer so the eval script can run
    standalone. Matches the fields HouseGrammar reads from a Plot.
    """
    from types import SimpleNamespace
    w = random.randint(min_w, max_w)
    d = random.randint(min_w, max_w)
    return SimpleNamespace(x=0, y=64, z=0, width=w, depth=d)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _mean_perplexity(model, sequences: list[list[str]]) -> float:
    """Return arithmetic mean perplexity across sequences."""
    if not sequences:
        return float("nan")
    return statistics.mean(model.perplexity(seq) for seq in sequences)


def _shuffle_sequences(sequences: list[list[str]]) -> list[list[str]]:
    """
    Return a copy of each sequence with tokens shuffled.

    Destroys all positional/transition structure while preserving vocabulary
    distribution — the correct random baseline for perplexity comparison.
    """
    result = []
    for seq in sequences:
        s = list(seq)
        random.shuffle(s)
        result.append(s)
    return result


def _print_report(
    good_pp:     float,
    bad_pp:      float,
    random_pp:   float,
    n_good:      int,
    n_bad:       int,
    ngram_order: int,
    alpha:       float,
) -> None:
    sep = "─" * 60
    print(f"\n{sep}")
    print("  House N-gram Scorer — Evaluation Report")
    print(sep)
    print(f"  N-gram order : {ngram_order}  |  Laplace α : {alpha}")
    print(sep)
    print(f"  {'Group':<20}  {'N':>6}  {'Mean perplexity':>16}")
    print(f"  {'─'*20}  {'─'*6}  {'─'*16}")
    print(f"  {'Good houses':<20}  {n_good:>6}  {good_pp:>16.2f}")
    print(f"  {'Bad houses':<20}  {n_bad:>6}  {bad_pp:>16.2f}")
    print(f"  {'Random baseline':<20}  {n_good:>6}  {random_pp:>16.2f}")
    print(sep)

    if good_pp < bad_pp < random_pp:
        print("  ✓ Expected ordering: good < bad < random")
    else:
        print("  ✗ Unexpected ordering — inspect training data or smoothing α")

    print()
    print("  Report snippet:")
    print(f'  "The grammar generates houses with mean perplexity {good_pp:.1f}')
    print(f'   (n={ngram_order}, α={alpha}), versus {bad_pp:.1f} for structurally')
    print(f'   rejected houses and {random_pp:.1f} for a shuffled random baseline."')
    print(sep + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(
    n_houses:     int,
    ngram_order:  int,
    alpha:        float,
    blend_weight: float,
    model_out:    Path,
    dry_run:      bool,
    palette_name: str,
) -> None:
    from data.biome_palettes import get_biome_palette
    from structures.house.house_ngram_scorer import (
        BlockSequenceRecorder,
        NgramLanguageModel,
        HouseNgramScorer,
    )
    from structures.house.house_scorer import HouseScorer
    from structures.house.house_grammar import HouseGrammar

    palette   = get_biome_palette(palette_name)
    rf_scorer = HouseScorer.load(
        Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"
    )
    editor = NullEditor() if dry_run else _get_live_editor()

    # Split evenly: first half good, second half explicitly bad.
    # This guarantees structurally distinct sequences so the n-gram model
    # has meaningful signal to learn from.
    n_good_target = n_houses // 2
    good_seqs: list[list[str]] = []
    bad_seqs:  list[list[str]] = []

    logger.info("Running %d grammar builds (dry_run=%s)…", n_houses, dry_run)

    for i in range(n_houses):
        force_bad = (i >= n_good_target)
        plot      = _random_plot()
        recorder  = BlockSequenceRecorder(editor)
        grammar   = HouseGrammar(recorder, palette, scorer=rf_scorer)

        try:
            ctx    = grammar._make_context(
                plot,
                rotation=random.choice([0, 90, 180, 270]),
                force_bad=force_bad,
            )
            params = grammar._ctx_to_params(ctx)
            grammar._place(ctx)
        except Exception as exc:
            logger.warning("Build %d failed: %s", i, exc)
            recorder.reset()
            continue

        seq = recorder.finish()
        if force_bad:
            bad_seqs.append(seq)
        else:
            good_seqs.append(seq)

    logger.info("Collected %d good, %d bad sequences.", len(good_seqs), len(bad_seqs))

    if not good_seqs:
        logger.error("No good sequences collected — cannot train model.")
        return

    # Train on good sequences only
    model = NgramLanguageModel(n=ngram_order, alpha=alpha)
    model.fit(good_seqs)

    # Evaluate all three groups
    good_pp   = _mean_perplexity(model, good_seqs)
    bad_pp    = _mean_perplexity(model, bad_seqs) if bad_seqs else float("nan")
    random_pp = _mean_perplexity(model, _shuffle_sequences(good_seqs))

    _print_report(good_pp, bad_pp, random_pp, len(good_seqs), len(bad_seqs), ngram_order, alpha)

    # Save model
    scorer = HouseNgramScorer(model=model, blend_weight=blend_weight)
    scorer.save(model_out)
    logger.info("Model saved to %s", model_out)


def _get_live_editor():
    from gdpc.editor import Editor
    editor = Editor(buffering=True)
    editor.checkConnection()
    return editor


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train and evaluate the house block-sequence n-gram scorer."
    )
    p.add_argument("--n-houses",     type=int,   default=300,
                   help="Number of houses to generate (half good, half bad). Default: 300")
    p.add_argument("--ngram-order",  type=int,   default=3, choices=[2, 3],
                   help="N-gram order: 2=bigram, 3=trigram. Default: 3")
    p.add_argument("--alpha",        type=float, default=0.1,
                   help="Laplace smoothing constant. Default: 0.1")
    p.add_argument("--blend-weight", type=float, default=0.25,
                   help="Runtime blend weight for HouseGrammar. Default: 0.25")
    p.add_argument("--model-out",    type=Path,
                   default=Path(__file__).parent.parent / "models" / "house_ngram.pkl",
                   help="Output path for the trained model.")
    p.add_argument("--dry-run",      action="store_true",
                   help="Use NullEditor — no Minecraft connection required.")
    p.add_argument("--palette",      default="medieval",
                   help="Biome palette name. Default: medieval")
    p.add_argument("--log-level",    default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="Logging verbosity. Default: INFO")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s  %(name)s  %(message)s",
    )
    run(
        n_houses     = args.n_houses,
        ngram_order  = args.ngram_order,
        alpha        = args.alpha,
        blend_weight = args.blend_weight,
        model_out    = args.model_out,
        dry_run      = args.dry_run,
        palette_name = args.palette,
    )