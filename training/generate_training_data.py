"""Updated training data generator for the new House system."""
import argparse
import csv
import random
from pathlib import Path
import matplotlib.pyplot as plt
from structures.house.house_scorer import HouseParams, ROOF_TYPES

def sample_params() -> HouseParams:
    """Samples parameters based on the new system's constraints."""
    role = random.choice(["house", "cottage"])
    # Houses are typically larger, cottages are smaller
    if role == "cottage":
        w, d = random.randint(5, 7), random.randint(5, 7)
        wall_h = random.randint(3, 5)
    else:
        w, d = random.randint(7, 11), random.randint(7, 11)
        wall_h = random.randint(5, 7)

    return HouseParams(
        w=w, d=d,
        wall_h=wall_h,
        structure_role=role,
        roof_type=random.choice(list(ROOF_TYPES.keys())),
        has_upper=(wall_h > 5),
        has_chimney=random.random() > 0.7,
        has_porch=random.random() > 0.8
    )

def render_preview(params: HouseParams):
    """Simple 2D elevation to help you score the house proportions."""
    plt.clf()
    # Draw Foundation/Ground
    plt.plot([0, params.w], [0, 0], 'k-', lw=3)
    # Draw Walls
    color = 'brown' if params.structure_role == "cottage" else 'gray'
    plt.gca().add_patch(plt.Rectangle((0, 0), params.w, params.wall_h, color=color, alpha=0.3))
    # Draw Roof
    plt.plot([0, params.w/2, params.w], [params.wall_h, params.wall_h + 3, params.wall_h], 'r-')
    plt.title(f"Role: {params.structure_role} | {params.w}x{params.d} | Height: {params.wall_h}")
    plt.axis('equal')
    plt.draw()

def run_session(n_samples, out_path):
    # Ensure directories exist
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = HouseParams.feature_names() + ["score"]
    
    with open(out_path, "a" if out_path.exists() else "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not out_path.exists() or out_path.stat().st_size == 0:
            writer.writeheader()

        plt.ion()
        plt.show()
        for i in range(n_samples):
            p = sample_params()
            render_preview(p)
            val = input(f"[{i+1}/{n_samples}] Score 0.0-1.0 (or 'q' to quit): ")
            if val.lower() == 'q': break
            try:
                row = {
                    "w": p.w, "d": p.d, "wall_h": p.wall_h, 
                    "role": p.structure_role, "roof": p.roof_type, 
                    "upper": int(p.has_upper), "chimney": int(p.has_chimney),
                    "porch": int(p.has_porch), "aspect": p.aspect_ratio,
                    "score": float(val)
                }
                writer.writerow(row)
            except ValueError: continue

if __name__ == "__main__":
    run_session(50, Path("data/house_labels.csv"))