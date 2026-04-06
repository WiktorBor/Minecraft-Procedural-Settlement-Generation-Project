"""
N-gram language model scorer for house block sequences.

Architecture
------------
Three cooperating classes:

    BlockSequenceRecorder
        Wraps an Editor and intercepts every placeBlock call during a grammar
        run, collecting the sequence of block IDs placed.  The grammar code
        needs no changes — swap the real editor for a recording one, run
        build(), then call recorder.finish() to retrieve the sequence.

    NgramLanguageModel
        Bigram + trigram model with Laplace smoothing.  Trained on a corpus
        of block-ID sequences from "good" houses (those that pass the
        HouseScorer threshold).  Exposes perplexity() for scoring.

    HouseNgramScorer
        Glues the two together.  Provides:
          • score(sequence) -> float   — perplexity converted to [0, 1]
          • save / load                — pickle persistence alongside the
                                         RandomForest model
          • blend_weight              — configurable mix with HouseScorer

Runtime integration (in house_grammar.py)
------------------------------------------
    If HouseGrammar receives a HouseNgramScorer it blends the perplexity
    score into the existing loop:

        final_score = (1 - w) * rf_score + w * ngram_score

    where w = ngram_scorer.blend_weight  (default 0.25).

Offline evaluation (eval_house_ngram.py)
-----------------------------------------
    The eval script runs the grammar N times, labels each run good/bad via
    HouseScorer, trains on good sequences, then reports:

        Good houses  perplexity: P1
        Bad houses   perplexity: P2
        Random baseline          P3

    P1 < P2 < P3 is the expected result and gives two clean report numbers.

Usage
-----
    # Training (done by eval_house_ngram.py — not called at runtime)
    recorder = BlockSequenceRecorder(editor)
    grammar  = HouseGrammar(recorder, palette)
    grammar.build(plot)
    seq = recorder.finish()

    model = NgramLanguageModel(n=3)
    model.fit([seq1, seq2, ...])

    scorer = HouseNgramScorer(model, blend_weight=0.25)
    scorer.save("models/house_ngram.pkl")

    # Runtime
    scorer = HouseNgramScorer.load("models/house_ngram.pkl")
    grammar = HouseGrammar(editor, palette, ngram_scorer=scorer)
"""
from __future__ import annotations

import logging
import math
import pickle
from collections import defaultdict
from pathlib import Path


from gdpc import Block

logger = logging.getLogger(__name__)

# Score returned when no model is loaded or a sequence is empty.
_FALLBACK_SCORE = 0.5

# Perplexity values above this are treated as the worst possible score.
# Calibrate by looking at eval output — random baselines typically sit
# well above 200 for a vocabulary of ~50 block types.
_MAX_PERPLEXITY = 300.0

def _nested_int():
    return defaultdict(int)

# ---------------------------------------------------------------------------
# BlockSequenceRecorder — transparent editor wrapper
# ---------------------------------------------------------------------------

class BlockSequenceRecorder:
    """
    Records every block ID placed via the BlockBuffer interface.

    Implements the same place() / place_many() interface as BlockBuffer so
    it can be used as a drop-in ctx.buffer during grammar probing — no real
    world writes happen, only the block sequence is captured.

    Example
    -------
        recorder = BlockSequenceRecorder()
        temp_ctx = replace(ctx, buffer=recorder)
        grammar._do_place(temp_ctx)
        sequence = recorder.finish()   # list[str] of block IDs
    """

    def __init__(self) -> None:
        self._sequence: list[str] = []
        self._base_y:   int | None = None

    # ------------------------------------------------------------------
    # BlockBuffer interface — intercept place/place_many
    # ------------------------------------------------------------------

    def place(self, _x: int, y: int, _z: int, block: Block) -> None:
        """Record placement without writing to the world."""
        if self._base_y is None:
            self._base_y = int(y)
        self._record(block, int(y))

    def place_many(self, positions, block: Block) -> None:
        """Record multiple placements without writing to the world."""
        for pos in positions:
            y = int(pos[1])
            if self._base_y is None:
                self._base_y = y
            self._record(block, y)

    def _record(self, block: Block, y: int) -> None:
        y_rel = y - (self._base_y or y)
        layer = "floor" if y_rel <= 1 else "wall" if y_rel <= 5 else "roof"
        self._sequence.append(f"{block.id}:{layer}")

    # ------------------------------------------------------------------
    # Sequence access
    # ------------------------------------------------------------------

    def finish(self) -> list[str]:
        """
        Return the recorded sequence and reset the internal buffer.

        Call once per house build.  The returned list is a snapshot —
        subsequent builds will not affect it.
        """
        seq = list(self._sequence)
        self._sequence.clear()
        self._base_y = None
        return seq

    def reset(self) -> None:
        """Discard the current recording without returning it."""
        self._sequence.clear()
        self._base_y = None

# ---------------------------------------------------------------------------
# NgramLanguageModel
# ---------------------------------------------------------------------------

class NgramLanguageModel:
    """
    Bigram + trigram language model over block-ID token sequences.

    Trained on a corpus of sequences from "good" houses.  Perplexity is
    computed as the geometric mean of per-token probabilities under the
    model, interpolated between bigram and trigram with Laplace smoothing.

    Attributes
    ----------
    n           : maximum n-gram order (2 or 3)
    alpha       : Laplace smoothing constant (default 0.1 — mild smoothing)
    interpolate : weight given to trigram vs bigram (only used when n=3)
    """

    def __init__(
        self,
        n: int = 3,
        alpha: float = 0.1,
        interpolate: float = 0.7,
    ) -> None:
        if n not in (2, 3):
            raise ValueError("n must be 2 or 3")
        self.n           = n
        self.alpha       = alpha
        self.interpolate = interpolate   # trigram weight; (1-w) goes to bigram

        # Counts filled by fit()
        self._unigram:  dict[str, int]              = defaultdict(int)
        self._bigram:   dict[tuple, dict[str, int]] = defaultdict(_nested_int)
        self._trigram:  dict[tuple, dict[str, int]] = defaultdict(_nested_int)
        self._vocab:    set[str]                    = set()
        self._fitted:   bool                        = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(self, sequences: list[list[str]]) -> "NgramLanguageModel":
        """
        Train on a list of block-ID sequences.

        Each sequence is one house build.  A special <S> start token is
        prepended so the first real token can be scored.

        Args:
            sequences: List of block-ID lists, one per house.

        Returns:
            self (for chaining).
        """
        self._unigram.clear()
        self._bigram.clear()
        self._trigram.clear()
        self._vocab.clear()

        for seq in sequences:
            padded = ["<S>", "<S>"] + seq + ["</S>"]
            for tok in padded:
                self._vocab.add(tok)
                self._unigram[tok] += 1
            for i in range(1, len(padded)):
                ctx1 = (padded[i - 1],)
                self._bigram[ctx1][padded[i]] += 1
            if self.n >= 3:
                for i in range(2, len(padded)):
                    ctx2 = (padded[i - 2], padded[i - 1])
                    self._trigram[ctx2][padded[i]] += 1

        V = len(self._vocab)
        logger.info(
            "NgramLanguageModel fitted: %d sequences, vocab=%d, order=%d",
            len(sequences), V, self.n,
        )
        self._vocab_size = V
        self._fitted = True
        return self

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _bigram_prob(self, context: str, token: str) -> float:
        """Laplace-smoothed bigram P(token | context)."""
        ctx       = (context,)
        numerator = self._bigram[ctx].get(token, 0) + self.alpha
        denominator = sum(self._bigram[ctx].values()) + self.alpha * self._vocab_size
        return numerator / denominator

    def _trigram_prob(self, ctx1: str, ctx2: str, token: str) -> float:
        """Laplace-smoothed trigram P(token | ctx1, ctx2)."""
        ctx       = (ctx1, ctx2)
        numerator = self._trigram[ctx].get(token, 0) + self.alpha
        denominator = sum(self._trigram[ctx].values()) + self.alpha * self._vocab_size
        return numerator / denominator

    def log_prob(self, sequence: list[str]) -> float:
        """
        Return the mean log-probability of the sequence under the model.

        Uses linear interpolation between bigram and trigram when n=3.
        Returns -inf for empty sequences.
        """
        if not self._fitted or not sequence:
            return float("-inf")

        padded = ["<S>", "<S>"] + sequence + ["</S>"]
        log_sum = 0.0
        count   = 0

        for i in range(2, len(padded)):
            tok  = padded[i]
            bp   = self._bigram_prob(padded[i - 1], tok)

            if self.n == 3:
                tp = self._trigram_prob(padded[i - 2], padded[i - 1], tok)
                p  = self.interpolate * tp + (1 - self.interpolate) * bp
            else:
                p = bp

            log_sum += math.log(max(p, 1e-12))
            count   += 1

        return log_sum / count if count > 0 else float("-inf")

    def perplexity(self, sequence: list[str]) -> float:
        """
        Return perplexity of the sequence.  Lower = more coherent.

        Perplexity = exp(-mean log P).  Returns _MAX_PERPLEXITY for
        empty or unscoreable sequences.
        """
        lp = self.log_prob(sequence)
        if lp == float("-inf"):
            return _MAX_PERPLEXITY
        return math.exp(-lp)


# ---------------------------------------------------------------------------
# HouseNgramScorer
# ---------------------------------------------------------------------------

class HouseNgramScorer:
    """
    Wraps a trained NgramLanguageModel and converts perplexity to a
    [0, 1] score compatible with the HouseScorer pipeline.

    Score mapping
    -------------
    perplexity=1        → score=1.0  (perfect — every transition seen before)
    perplexity=MAX      → score=0.0  (chaotic — nothing recognised)
    mapping is linear in log space for smooth gradients.

    Attributes
    ----------
    blend_weight : float
        When used at runtime in HouseGrammar, this controls how much weight
        the n-gram score gets relative to the RandomForest score.
        final = (1 - blend_weight) * rf_score + blend_weight * ngram_score
    """

    def __init__(
        self,
        model: NgramLanguageModel | None = None,
        blend_weight: float = 0.25,
    ) -> None:
        self.model        = model
        self.blend_weight = blend_weight

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path, blend_weight: float = 0.25) -> "HouseNgramScorer":
        """
        Load a trained model from a .pkl file.

        Falls back to a no-op scorer (always returns 0.5) if the file does
        not exist, mirroring HouseScorer.load() behaviour.
        """
        p = Path(path)
        if not p.exists():
            logger.warning(
                "HouseNgramScorer: model file %s not found — using fallback score %.2f. "
                "Run eval_house_ngram.py to train the model.",
                p, _FALLBACK_SCORE,
            )
            return cls(model=None, blend_weight=blend_weight)

        with open(p, "rb") as f:
            model = pickle.load(f)
        logger.info("HouseNgramScorer: loaded model from %s", p)
        return cls(model=model, blend_weight=blend_weight)

    def save(self, path: str | Path) -> None:
        """Pickle the inner NgramLanguageModel to path."""
        if self.model is None:
            raise RuntimeError("No model to save — call fit() first.")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump(self.model, f)
        logger.info("HouseNgramScorer: model saved to %s", p)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def perplexity_to_score(self, perplexity: float) -> float:
        """
        Map perplexity ∈ [1, _MAX_PERPLEXITY] to score ∈ [0, 1].

        Uses log scale so mid-range perplexity doesn't collapse to ~0.
        """
        perplexity = max(1.0, min(perplexity, _MAX_PERPLEXITY))
        log_pp     = math.log(perplexity)
        log_max    = math.log(_MAX_PERPLEXITY)
        return 1.0 - (log_pp / log_max)

    def score(self, sequence: list[str]) -> float:
        """
        Score a block sequence.  Returns float in [0, 1].

        Args:
            sequence: List of block IDs from BlockSequenceRecorder.finish().

        Returns:
            1.0 for perfectly familiar sequences, 0.0 for chaotic ones.
            Returns _FALLBACK_SCORE if no model is loaded or sequence is empty.
        """
        if self.model is None or not sequence:
            return _FALLBACK_SCORE
        pp = self.model.perplexity(sequence)
        return self.perplexity_to_score(pp)

    def blend(self, rf_score: float, sequence: list[str]) -> float:
        """
        Blend a RandomForest score with the n-gram score.

        Args:
            rf_score: Score from HouseScorer.score() ∈ [0, 1].
            sequence: Block sequence from the same build.

        Returns:
            Weighted combination ∈ [0, 1].
        """
        if self.model is None:
            return rf_score
        ngram_score = self.score(sequence)
        w = self.blend_weight
        return (1.0 - w) * rf_score + w * ngram_score