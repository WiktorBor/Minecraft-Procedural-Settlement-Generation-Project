"""
Aesthetic scorer for the house shape grammar.
Integrates RandomForest (Shape) and N-gram (Pattern) models.
"""
from __future__ import annotations

import logging
import pickle
import os
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.55 

# Numeric encoding for the ML model to match HouseParams.to_feature_vector
ROOF_TYPES = {"gabled": 0, "steep": 1, "cross": 2}
ROLE_TYPES = {"house": 0, "cottage": 1}

@dataclass
class HouseParams:
    """
    A parameter bundle representing a proposed house build.
    Used by the Orchestrator to judge designs before building.
    """
    w:              int    
    d:              int    
    wall_h:         int    
    structure_role: str    
    roof_type:      str    
    has_upper:      bool   
    has_chimney:    bool   = False
    has_porch:      bool   = False
    bridge_side:    str | None = None

    @property
    def aspect_ratio(self) -> float:
        """Calculates the ratio of the longest side to the shortest side."""
        return max(self.w, self.d) / max(min(self.w, self.d), 1)

    def to_feature_vector(self) -> np.ndarray:
        """
        Convert to a numeric array of EXACTLY 9 features.
        The order here MUST match the training columns.
        """
        return np.array([
            float(self.w),float(self.d),float(self.wall_h),
            float(ROLE_TYPES.get(self.structure_role, 0)),
            float(ROOF_TYPES.get(self.roof_type, 0)),
            float(self.has_upper),
            float(self.has_chimney),
            float(self.has_porch),
            (max(self.w, self.d) / min(self.w, self.d))
        ], dtype=np.float32)

    @staticmethod
    def feature_names() -> list[str]:
        """Ensures training and scoring always use the same column names."""
        return ["w", "d", "wall_h", "role_num", "roof_num", "upper", "chimney", "porch", "aspect"]


class HouseScorer:
    """
    Combines a RandomForest (Architectural Shape) and an N-gram (Block Patterns).
    """
    def __init__(self, model=None, ngram_model=None, threshold: float = DEFAULT_THRESHOLD) -> None:
        self._model = model          # The Shape Brain (RandomForest)
        self._ngram = ngram_model    # The Pattern Brain (N-gram)
        self.threshold = threshold

    @staticmethod
    def train_and_save(csv_path: str, model_output_path: str):
        """
        Trains the RandomForest using the 9-feature vector system.
        """
        print(f"Training ML model on {csv_path}...")
        df = pd.read_csv(csv_path)
        
        # 1. Ensure string columns are mapped to the same numbers as HouseParams
        df['role_num'] = df['role'].map(ROLE_TYPES).fillna(0)
        df['roof_num'] = df['roof_type'].map(ROOF_TYPES).fillna(0)
        # Handle boolean conversion for CSV rows
        df['upper'] = df['has_upper'].astype(float)
        df['chimney'] = df['has_chimney'].astype(float)
        df['porch'] = df['has_porch'].astype(float)
        df['aspect'] = df.apply(lambda r: max(r['w'], r['d']) / max(min(r['w'], r['d']), 1), axis=1)
        
        # 2. Extract the exact 9 features
        feature_cols = HouseParams.feature_names()
        X = df[feature_cols]
        y = df["score"]
        
        # 3. Train and Save
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
        with open(model_output_path, "wb") as f:
            pickle.dump(model, f)
        print(f"Success: Model saved to {model_output_path}")

    @classmethod
    def load(cls, path: str | Path = "models/house_scorer.pkl", 
             ngram_path: str | Path = "models/house_ngram_scorer.pkl",
             threshold: float = DEFAULT_THRESHOLD) -> "HouseScorer":
        """Loads both ML models if available, otherwise falls back to heuristics."""
        rf_model = None
        ngram_model = None

        # Load Shape Model
        if Path(path).exists():
            with open(path, "rb") as f:
                rf_model = pickle.load(f)
        else:
            logger.warning(f"Shape model {path} not found.")

        # Load Pattern Model (N-gram)
        if Path(ngram_path).exists():
            with open(ngram_path, "rb") as f:
                ngram_model = pickle.load(f)
        
        return cls(model=rf_model, ngram_model=ngram_model, threshold=threshold)

    def score(self, params: HouseParams, block_sequence: list[str] | None = None) -> float:
        """
        Calculates a blended score.
        70% Shape (RandomForest) + 30% Pattern (N-gram).
        """
        # 1. Get Shape Score
        shape_score = 0.5
        if self._model is not None:
            x_raw = params.to_feature_vector().reshape(1, -1)
            x_df = pd.DataFrame(x_raw, columns=HouseParams.feature_names())
            shape_score = float(self._model.predict(x_df)[0])
        else:
            shape_score = self._heuristic_score(params)
        
        # 2. Get Pattern Score (if N-gram exists and sequence is provided)
        pattern_score = 1.0
        if block_sequence and self._ngram is not None:
            # Assumes the N-gram model has a get_sequence_probability method
            try:
                pattern_score = self._ngram.get_sequence_probability(block_sequence)
            except AttributeError:
                pass

        # 3. Blend and Clip
        final = (shape_score * 0.7) + (pattern_score * 0.3)
        return float(np.clip(final, 0.0, 1.0))

    def _heuristic_score(self, params: HouseParams) -> float:
        """Mathematical fallback if no ML model is trained."""
        s = 0.5
        if params.structure_role == "cottage":
            s += 0.1 if (params.w <= 7 and params.d <= 7) else -0.2
        if params.wall_h > params.w or params.wall_h > params.d:
            s -= 0.15
        if params.aspect_ratio > 2.0:
            s -= 0.1
        return float(np.clip(s, 0.0, 1.0))