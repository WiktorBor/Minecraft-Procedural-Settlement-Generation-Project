"""
train_scorer.py
---------------
1. Rescores house_labels.csv using the updated 9-feature HouseScorer heuristics.
2. Trains a RandomForestRegressor on those rescored labels.
"""
from __future__ import annotations

import pandas as pd
from pathlib import Path
from structures.house.house_scorer import HouseScorer, HouseParams

def rescore_csv(input_path: str, output_path: str):
    """
    Uses the HouseScorer's internal heuristic logic to assign a score to 
    every house in the CSV, ensuring the AI has consistent data to learn from.
    """
    df = pd.read_csv(input_path)
    scorer = HouseScorer() # Uses internal fallback _heuristic_score logic
    
    new_scores = []
    print(f"Rescoring {len(df)} samples...")
    
    for _, row in df.iterrows():
        # Reconstruct the 9-feature parameter bundle from the CSV row
        # NOTE: Ensure these column names match your house_labels.csv exactly
        p = HouseParams(
            w=int(row['w']), 
            d=int(row['d']), 
            wall_h=int(row['wall_h']),
            structure_role=row['role'], 
            roof_type=row['roof_type'],
            has_upper=bool(row['has_upper']), 
            has_chimney=bool(row['has_chimney']),
            has_porch=bool(row['has_porch']),
            bridge_side=row['bridge_side'] if 'bridge_side' in row else None        )
        # Apply the heuristic 'Teacher' score
        new_scores.append(scorer.score(p))
    
    df['score'] = new_scores
    df.to_csv(output_path, index=False)
    print(f"Success: Rescored file saved to {output_path}")

if __name__ == "__main__":
    # 1. Define Paths
    INPUT_CSV = "training/house_labels.csv"
    CLEANED_CSV = "training/house_labels_rescored.csv"
    MODEL_PATH = "models/house_scorer.pkl"

    # 2. Ensure directories exist
    Path("models").mkdir(exist_ok=True)

    # 3. Rescore the data (Passing BOTH arguments now)
    if Path(INPUT_CSV).exists():
        rescore_csv(INPUT_CSV, CLEANED_CSV)
    else:
        print(f"Error: Could not find {INPUT_CSV}")
        exit(1)
    
    # 4. Train the actual Random Forest 'Brain' using the rescored data
    HouseScorer.train_and_save(CLEANED_CSV, MODEL_PATH)