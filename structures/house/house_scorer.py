"""
Aesthetic scorer for the house shape grammar.

Architecture
------------
The scorer is a thin wrapper around a scikit-learn RandomForestClassifier
trained on labelled grammar-parameter sets.  It answers one question:

    "Given this set of grammar parameters, is the resulting house
     likely to look good?"

The model is trained offline using generate_training_data.py and saved as
a .pkl file.  At runtime the scorer loads that file once and scores each
proposed parameter set before any blocks are placed.

Feature vector (11 features, all numeric)
------------------------------------------
    w, d              — footprint dimensions (int)
    wall_h            — lower storey wall height (int 3-5)
    has_upper         — upper storey present (0/1)
    upper_h           — upper storey height (int 0-3)
    has_chimney       — chimney present (0/1)
    has_porch         — porch present (0/1)
    has_extension     — lean-to extension present (0/1)
    roof_type         — 0=gabled, 1=steep, 2=cross
    foundation_h      — foundation depth (int 1-2)
    aspect_ratio      — max(w,d) / min(w,d) (float)

Label
-----
    score: float 0.0–1.0  (collected from you during training)
    The model is trained as a regressor (RandomForestRegressor) so it
    outputs a continuous score rather than a binary class.

Usage
-----
    scorer = HouseScorer.load("models/house_scorer.pkl")
    params = HouseParams(w=8, d=8, wall_h=4, ...)
    score  = scorer.score(params)          # 0.0 – 1.0
    if score >= scorer.threshold:
        grammar.build_from_params(plot, params)
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Default threshold — only build houses scoring at or above this.
# Can be overridden at construction time.
DEFAULT_THRESHOLD = 0.65

# Roof type encoding (must match generate_training_data.py)
ROOF_TYPES = {"gabled": 0, "steep": 1, "cross": 2}
ROOF_TYPES_INV = {v: k for k, v in ROOF_TYPES.items()}


# ---------------------------------------------------------------------------
# Parameter dataclass — the feature vector in a named, type-safe form
# ---------------------------------------------------------------------------

@dataclass
class HouseParams:
    """
    A fully-specified set of grammar parameters for one house.

    All fields are the exact inputs the grammar needs — generating a
    HouseParams and scoring it is cheap (no blocks placed, no GDPC calls).
    """
    w:              int    # footprint width  (blocks)
    d:              int    # footprint depth  (blocks)
    wall_h:         int    # lower wall height (3–5)
    has_upper:      bool   # upper storey present
    upper_h:        int    # upper storey height (0 if not has_upper)
    has_chimney:    bool   # chimney present
    has_porch:      bool   # porch present
    has_extension:  bool   # lean-to extension present
    roof_type:      str    # "gabled" | "steep" | "cross"
    foundation_h:   int    # foundation depth (1–2)
    ext_w:          int    # extension width (0 if not has_extension)

    @property
    def aspect_ratio(self) -> float:
        return max(self.w, self.d) / max(min(self.w, self.d), 1)

    def to_feature_vector(self) -> np.ndarray:
        """Convert to the 11-element float32 array the model expects."""
        return np.array([
            float(self.w),
            float(self.d),
            float(self.wall_h),
            float(self.has_upper),
            float(self.upper_h),
            float(self.has_chimney),
            float(self.has_porch),
            float(self.has_extension),
            float(ROOF_TYPES.get(self.roof_type, 0)),
            float(self.foundation_h),
            self.aspect_ratio,
            float(self.ext_w),
        ], dtype=np.float32)

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "w", "d", "wall_h", "has_upper", "upper_h",
            "has_chimney", "has_porch", "has_extension",
            "roof_type", "foundation_h", "aspect_ratio", "ext_w",
        ]


# ---------------------------------------------------------------------------
# Scorer — loads a trained model and scores HouseParams instances
# ---------------------------------------------------------------------------

class HouseScorer:
    """
    Wraps a trained RandomForestRegressor to score grammar parameter sets.

    If no model file is found, falls back to a heuristic scorer so the
    grammar still works without training data.
    """

    def __init__(
        self,
        model=None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._model    = model
        self.threshold = threshold

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path, threshold: float = DEFAULT_THRESHOLD) -> "HouseScorer":
        """
        Load a trained model from a .pkl file.

        Falls back to heuristic scoring (no model) if the file does not
        exist, so the grammar degrades gracefully on a fresh install.
        """
        p = Path(path)
        if not p.exists():
            logger.warning(
                "HouseScorer: model file %s not found — using heuristic scorer. "
                "Run generate_training_data.py to create training data, then "
                "train_scorer.py to fit the model.",
                p,
            )
            return cls(model=None, threshold=threshold)

        with open(p, "rb") as f:
            model = pickle.load(f)
        logger.info("HouseScorer: loaded model from %s", p)
        return cls(model=model, threshold=threshold)

    @classmethod
    def train_and_save(
        cls,
        csv_path: str | Path,
        model_path: str | Path,
        threshold: float = DEFAULT_THRESHOLD,
        n_estimators: int = 200,
        random_state: int = 42,
    ) -> "HouseScorer":
        """
        Train a RandomForestRegressor from a labelled CSV and save it.

        CSV format (produced by generate_training_data.py):
            w,d,wall_h,has_upper,upper_h,has_chimney,has_porch,
            has_extension,roof_type,foundation_h,score

        Args:
            csv_path:    Path to the labelled CSV file.
            model_path:  Where to save the trained .pkl file.
            threshold:   Score threshold to use at inference time.
            n_estimators: Number of trees in the random forest.
            random_state: Seed for reproducibility.

        Returns:
            A HouseScorer instance wrapping the trained model.
        """
        try:
            import pandas as pd
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.model_selection import cross_val_score
            from sklearn.preprocessing import LabelEncoder
        except ImportError as e:
            raise ImportError(
                "Training requires pandas and scikit-learn: "
                "pip install pandas scikit-learn"
            ) from e

        df = pd.read_csv(csv_path)
        required = set(HouseParams.feature_names() + ["score"])
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV missing columns: {missing}")

        # Encode roof_type string → int
        df["roof_type"] = df["roof_type"].map(ROOF_TYPES).fillna(0).astype(int)

        X = df[HouseParams.feature_names()].values.astype(np.float32)
        y = df["score"].values.astype(np.float32)

        model = RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=random_state,
            max_depth=8,
            min_samples_leaf=2,
        )
        model.fit(X, y)

        # Cross-validation score for the report
        cv_scores = cross_val_score(model, X, y, cv=min(5, len(df) // 4), scoring="r2")
        logger.info(
            "HouseScorer trained: R²=%.3f ± %.3f  (n=%d samples, %d trees)",
            cv_scores.mean(), cv_scores.std(), len(df), n_estimators,
        )

        # Feature importance — useful for the report
        importances = sorted(
            zip(HouseParams.feature_names(), model.feature_importances_),
            key=lambda x: -x[1],
        )
        logger.info("Feature importances:")
        for name, imp in importances:
            logger.info("  %-20s %.3f", name, imp)

        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        logger.info("Model saved to %s", model_path)

        return cls(model=model, threshold=threshold)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score(self, params: HouseParams) -> float:
        """
        Return an aesthetic score in [0.0, 1.0] for the given parameters.

        Uses the trained model if available, otherwise falls back to the
        built-in heuristic.
        """
        if self._model is not None:
            x = params.to_feature_vector().reshape(1, -1)
            raw = float(self._model.predict(x)[0])
            return float(np.clip(raw, 0.0, 1.0))
        return self._heuristic_score(params)

    def passes(self, params: HouseParams) -> bool:
        """Return True if score >= threshold."""
        return self.score(params) >= self.threshold

    # ------------------------------------------------------------------
    # Heuristic fallback (no model required)
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_score(params: HouseParams) -> float:
        """
        Hand-crafted aesthetic rules derived from looking at good Minecraft
        medieval buildings.  Used when no trained model is available.

        Rules:
          - Upper storey improves score significantly
          - Chimney improves score
          - Very flat roofs (gabled on tiny footprint) look worse
          - Cross-gabled only looks good on large footprints
          - Extreme aspect ratios (very long thin) look odd
          - Porch adds character
          - Extensions add silhouette interest
        """
        s = 0.5   # baseline

        # Upper storey is the biggest visual differentiator
        if params.has_upper:
            s += 0.15

        # Chimney adds character
        if params.has_chimney:
            s += 0.08

        # Porch adds character
        if params.has_porch:
            s += 0.05

        # Extension breaks rectangular silhouette — good
        if params.has_extension:
            s += 0.06

        # Cross-gabled only suits large footprints
        if params.roof_type == "cross":
            if params.w >= 9 and params.d >= 9:
                s += 0.05
            else:
                s -= 0.30   # looks wrong on small buildings

        # Steep roof on small cottage looks great
        if params.roof_type == "steep" and params.w <= 7:
            s += 0.08

        # Tall walls without upper storey look like a box
        if params.wall_h >= 5 and not params.has_upper:
            s -= 0.10

        # Very small footprints shouldn't get upper storeys
        if params.has_upper and (params.w < 7 or params.d < 7):
            s -= 0.25

        # Extreme aspect ratios
        if params.aspect_ratio > 2.5:
            s -= 0.10

        # Deep foundation looks more embedded — slight bonus
        if params.foundation_h == 2:
            s += 0.03

        features = sum([
            params.has_upper,
            params.has_chimney,
            params.has_porch,
            params.has_extension,
        ])

        if features == 0:
            s -= 0.20

        return float(np.clip(s, 0.0, 1.0))