"""
rescore_labels.py
-----------------
Replaces the manual scores in house_labels.csv with scores from
HouseScorer._heuristic_score(), giving a full 0.0-1.0 spread that
the RandomForestRegressor can actually learn from.

Usage
-----
    python3 rescore_labels.py \
        --input  data/house_labels.csv \
        --output data/house_labels_rescored.csv

Then train the RF:
    python3 -m structures.house.house_scorer \
        --csv   data/house_labels_rescored.csv \
        --model models/house_scorer.pkl
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Inline heuristic — copied from HouseScorer so this script is self-contained
# and can be run without importing the full project.
# ---------------------------------------------------------------------------

import numpy as np


ROOF_TYPES = {"gabled": 0, "steep": 1, "cross": 2}


def heuristic_score(row: dict) -> float:
    w             = float(row["w"])
    d             = float(row["d"])
    wall_h        = float(row["wall_h"])
    has_upper     = float(row["has_upper"]) > 0.5
    has_chimney   = float(row["has_chimney"]) > 0.5
    has_porch     = float(row["has_porch"]) > 0.5
    has_extension = float(row["has_extension"]) > 0.5
    roof_type     = str(row["roof_type"]).strip()
    aspect_ratio  = max(w, d) / max(min(w, d), 1)

    s = 0.5

    if has_upper:
        s += 0.15
    if has_chimney:
        s += 0.08
    if has_porch:
        s += 0.05
    if has_extension:
        s += 0.06

    if roof_type == "cross":
        if w >= 9 and d >= 9:
            s += 0.05
        else:
            s -= 0.30

    if roof_type == "steep" and w <= 7:
        s += 0.08

    if wall_h >= 5 and not has_upper:
        s -= 0.10

    if has_upper and (w < 7 or d < 7):
        s -= 0.25

    if aspect_ratio > 2.5:
        s -= 0.10

    if float(row.get("foundation_h", 1)) == 2:
        s += 0.03

    features = sum([has_upper, has_chimney, has_porch, has_extension])
    if features == 0:
        s -= 0.20

    return float(np.clip(s, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def rescore(input_path: Path, output_path: Path) -> None:
    rows = []
    with open(input_path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            row["score"] = f"{heuristic_score(row):.4f}"
            rows.append(row)

    # Ensure score column exists
    if "score" not in fieldnames:
        fieldnames = list(fieldnames) + ["score"]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    scores = [float(r["score"]) for r in rows]
    print(f"Rescored {len(rows)} rows.")
    print(f"  min={min(scores):.2f}  max={max(scores):.2f}  "
          f"mean={sum(scores)/len(scores):.2f}")
    print(f"  Distribution:")
    bands = [(0.0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.01)]
    for lo, hi in bands:
        count = sum(1 for s in scores if lo <= s < hi)
        bar   = "█" * count
        print(f"    [{lo:.1f}-{hi:.1f})  {bar}  ({count})")
    print(f"\nSaved to {output_path}")
    print(f"\nNext step — train the RF model:")
    print(f"  python3 -c \"")
    print(f"  from structures.house.house_scorer import HouseScorer")
    print(f"  HouseScorer.train_and_save('{output_path}', 'models/house_scorer.pkl')\"")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rescore house_labels.csv using the heuristic scorer.")
    p.add_argument("--input",  type=Path, default=Path("data/house_labels.csv"))
    p.add_argument("--output", type=Path, default=Path("data/house_labels_rescored.csv"))
    return p.parse_args()


if __name__ == "__main__":
    args = _parse()
    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rescore(args.input, args.output)