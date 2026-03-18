"""
Train the HouseScorer model from labelled CSV data.

Usage
-----
    python train_scorer.py --data data/house_labels.csv --out models/house_scorer.pkl

    # With custom threshold and cross-validation report:
    python train_scorer.py --data data/house_labels.csv --out models/house_scorer.pkl
                           --threshold 0.6 --trees 300

The script prints a cross-validation R² score and feature importances —
both are useful content for your project report.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from structures.house.house_scorer import HouseScorer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the HouseScorer model.")
    parser.add_argument("--data",      required=True,
                        help="Path to labelled CSV (from generate_training_data.py).")
    parser.add_argument("--out",       default="models/house_scorer.pkl",
                        help="Where to save the trained model.")
    parser.add_argument("--threshold", type=float, default=0.55,
                        help="Aesthetic threshold used at inference time (default 0.55).")
    parser.add_argument("--trees",     type=int,   default=200,
                        help="Number of trees in the random forest (default 200).")
    args = parser.parse_args()

    scorer = HouseScorer.train_and_save(
        csv_path=args.data,
        model_path=args.out,
        threshold=args.threshold,
        n_estimators=args.trees,
    )
    print(f"\nModel saved to {args.out}")
    print(f"Threshold: {args.threshold}")
    print("Integration: pass model_path to HouseGrammar in house_builder.py")