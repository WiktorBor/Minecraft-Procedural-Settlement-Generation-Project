"""
Training data generator for the HouseScorer.

Run this script standalone (no Minecraft connection needed) to:
  1. Randomly sample grammar parameter sets.
  2. Render a simple 2D side-elevation for each one using matplotlib.
  3. Prompt you to score each house 0.0–1.0 based on how it looks.
  4. Save all labelled samples to a CSV ready for train_scorer.py.

Usage
-----
    python generate_training_data.py --samples 100 --out data/house_labels.csv

    # Resume a previous session (appends to existing CSV):
    python generate_training_data.py --samples 50 --out data/house_labels.csv --resume

Controls (shown in the plot window)
-------------------------------------
    Keys 1-9  → score 0.1 – 0.9  (press the digit, window advances)
    Key 0     → score 1.0
    Key s     → skip (don't record this sample)
    Key q     → quit and save what you have so far

Tips for scoring
----------------
  0.0 – 0.3  Looks wrong: flat roof on stone box, wrong proportions, no features
  0.4 – 0.6  Acceptable but bland: correct but boring, missing character
  0.7 – 0.8  Good: interesting silhouette, features work together
  0.9 – 1.0  Excellent: looks like a real medieval building
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

import numpy as np

# Defer matplotlib import so CI/headless environments don't fail on import
try:
    import matplotlib
    import platform
    if platform.system() == "Darwin":
        matplotlib.use("MacOSX")
    else:
        matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Re-use the dataclass from house_scorer without importing gdpc
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root
from structures.house.house_scorer import HouseParams, ROOF_TYPES


# ---------------------------------------------------------------------------
# Random parameter sampler
# ---------------------------------------------------------------------------

def sample_params(rng: random.Random) -> HouseParams:
    """Sample a random HouseParams — same distribution as the grammar."""
    w = rng.randint(5, 14)
    d = rng.randint(5, 14)
    wall_h = rng.randint(3, 5)
    has_upper = (w >= 7 and d >= 6 and wall_h <= 4 and rng.random() < 0.55)
    upper_h = rng.randint(2, 3) if has_upper else 0
    has_chimney = rng.random() < 0.75
    has_porch = (w >= 7) and rng.random() < 0.40
    has_extension = (w >= 8 and d >= 8) and rng.random() < 0.35

    # Roof type — weighted same as grammar
    roof_type = rng.choices(
        ["gabled", "steep", "cross"],
        weights=[0.5, 0.3, 0.2],
    )[0]
    # Cross only valid on large plots
    if roof_type == "cross" and not (w >= 9 and d >= 9):
        roof_type = "gabled"

    foundation_h = rng.choice([1, 1, 2])

    ext_w = random.randint(3, max(3, w // 2)) if has_extension else 0

    return HouseParams(
        w=w, d=d, wall_h=wall_h,
        has_upper=has_upper, upper_h=upper_h,
        has_chimney=has_chimney, has_porch=has_porch,
        has_extension=has_extension,
        roof_type=roof_type, foundation_h=foundation_h,
        ext_w=ext_w,
    )


# ---------------------------------------------------------------------------
# 2D elevation renderer
# ---------------------------------------------------------------------------

PALETTE = {
    "foundation": "#7a7a7a",
    "wall":       "#c8a96e",
    "upper_wall": "#5a3a1a",   # darker timber frame
    "roof":       "#3a2a1a",
    "chimney":    "#9a9a9a",
    "window":     "#aaddff",
    "door":       "#4a2a0a",
    "porch_post": "#5a3a1a",
    "extension":  "#b09060",
    "sky":        "#e8f4f8",
    "ground":     "#5a8a3a",
}


def render_elevation(params: HouseParams, ax: "plt.Axes") -> None:
    """
    Draw a simple 2D front-elevation of the house on the given axes.

    All dimensions are in 'blocks' with 1 block = 1 unit.
    The elevation is centred horizontally, grounded at y=0.
    """
    ax.set_facecolor(PALETTE["sky"])
    ax.set_aspect("equal")

    w  = params.w
    y0 = 0   # ground level

    # Ground strip
    ax.add_patch(mpatches.Rectangle(
        (-2, -params.foundation_h - 0.5), w + 4, params.foundation_h + 0.5,
        color=PALETTE["ground"], zorder=1,
    ))

    # Foundation
    ax.add_patch(mpatches.Rectangle(
        (0, y0 - params.foundation_h), w, params.foundation_h,
        color=PALETTE["foundation"], zorder=2,
    ))

    # Lower body walls
    body_top = y0 + params.wall_h
    ax.add_patch(mpatches.Rectangle(
        (0, y0), w, params.wall_h,
        color=PALETTE["wall"], zorder=2,
    ))

    # Windows in lower body (2 flanking door)
    door_x = w // 2
    win_y  = y0 + 2
    for wx in [door_x - 2, door_x + 2]:
        if 0 < wx < w - 1:
            ax.add_patch(mpatches.Rectangle(
                (wx + 0.1, win_y), 0.8, 1.0,
                color=PALETTE["window"], zorder=3,
            ))

    # Door
    ax.add_patch(mpatches.Rectangle(
        (door_x - 0.4, y0), 0.8, 2.0,
        color=PALETTE["door"], zorder=3,
    ))

    # Porch posts
    if params.has_porch:
        for px in [door_x - 1, door_x + 1]:
            ax.add_patch(mpatches.Rectangle(
                (px - 0.1, y0 - 0.3), 0.2, 2.2,
                color=PALETTE["porch_post"], zorder=3,
            ))

    # Upper storey (jetty overhangs by 0.5 each side)
    upper_base = body_top
    if params.has_upper:
        ax.add_patch(mpatches.Rectangle(
            (-0.5, upper_base), w + 1, params.upper_h,
            color=PALETTE["upper_wall"], zorder=2,
        ))
        # Upper windows
        uw_y = upper_base + 0.5
        for ux in range(1, w, 2):
            ax.add_patch(mpatches.Rectangle(
                (ux - 0.5 + 0.1, uw_y), 0.8, 0.8,
                color=PALETTE["window"], zorder=3,
            ))
        roof_base = upper_base + params.upper_h
    else:
        roof_base = body_top

    # Roof
    _render_roof(ax, params, w, roof_base)

    # Chimney
    if params.has_chimney:
        ch_x = w - 2
        ch_top = roof_base + w // 2 + 2
        ax.add_patch(mpatches.Rectangle(
            (ch_x, y0 + 1), 1, ch_top - y0 - 1,
            color=PALETTE["chimney"], zorder=4,
        ))
        # Smoke puff (circle)
        ax.add_patch(mpatches.Circle(
            (ch_x + 0.5, ch_top + 0.6), 0.4,
            color="#cccccc", alpha=0.6, zorder=5,
        ))

    # Extension (lean-to on right side, smaller)
    if params.has_extension:
        ext_w = params.ext_w
        ext_x = w
        ext_h = 3
        ax.add_patch(mpatches.Rectangle(
            (ext_x, y0), ext_w, ext_h,
            color=PALETTE["extension"], zorder=2,
        ))
        # Lean-to roof (simple triangle)
        roof_pts = np.array([
            [ext_x,         ext_h + y0],
            [ext_x + ext_w, ext_h + y0],
            [ext_x,         ext_h + y0 + 1],
        ])
        ax.add_patch(mpatches.Polygon(
            roof_pts, closed=True, color=PALETTE["roof"], zorder=3,
        ))

    # Axes labels
    ax.set_xlim(-2, w + (params.ext_w if params.has_extension else 0) + 4)
    ax.set_ylim(-params.foundation_h - 1, roof_base + w // 2 + 4)
    ax.set_xlabel("width (blocks)")
    ax.set_ylabel("height (blocks)")
    ax.grid(True, alpha=0.3, linewidth=0.5)


def _render_roof(ax: "plt.Axes", params: HouseParams, w: int, roof_base: float) -> None:
    """Draw the roof shape on the axes."""
    peak   = w // 2 + (1 if params.roof_type == "steep" else 0)
    cx     = w / 2

    if params.roof_type in ("gabled", "steep"):
        roof_pts = np.array([
            [0,  roof_base],
            [w,  roof_base],
            [cx, roof_base + peak],
        ])
        ax.add_patch(mpatches.Polygon(
            roof_pts, closed=True, color=PALETTE["roof"], zorder=3,
        ))

    elif params.roof_type == "cross":
        # Two overlapping triangles
        peak_z = w // 2
        for pts in [
            [[0, roof_base], [w, roof_base], [cx, roof_base + peak]],
            [[cx - 1, roof_base], [cx + 1, roof_base],
             [cx, roof_base + peak_z]],
        ]:
            ax.add_patch(mpatches.Polygon(
                np.array(pts), closed=True, color=PALETTE["roof"], zorder=3,
            ))


# ---------------------------------------------------------------------------
# Interactive labelling session
# ---------------------------------------------------------------------------

def run_labelling_session(
    n_samples: int,
    out_path: Path,
    resume: bool = False,
    seed: int = 42,
) -> None:
    """Run the interactive scoring session."""
    if not HAS_MATPLOTLIB:
        print("ERROR: matplotlib not installed. Run: pip install matplotlib")
        sys.exit(1)

    rng = random.Random(seed)

    # Load existing data if resuming
    existing: list[dict] = []
    if resume and out_path.exists():
        with open(out_path, newline="") as f:
            existing = list(csv.DictReader(f))
        print(f"Resuming — {len(existing)} samples already recorded.")

    fieldnames = HouseParams.feature_names() + ["score"]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mode = "a" if (resume and out_path.exists()) else "w"
    outfile = open(out_path, mode, newline="")
    writer  = csv.DictWriter(outfile, fieldnames=fieldnames)
    if mode == "w":
        writer.writeheader()

    scored = 0
    skipped = 0

    print("\n=== House Scoring Session ===")
    print("Press 1-9 to score 0.1-0.9, 0 for 1.0, s to skip, q to quit\n")

    for i in range(n_samples):
        params = sample_params(rng)

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(
            f"House {i+1}/{n_samples}  |  "
            f"{params.w}×{params.d} blocks  |  "
            f"{'2 storeys' if params.has_upper else '1 storey'}  |  "
            f"{params.roof_type} roof  |  "
            f"{'chimney  ' if params.has_chimney else ''}"
            f"{'porch  ' if params.has_porch else ''}"
            f"{'extension' if params.has_extension else ''}",
            fontsize=11,
        )

        # Front elevation
        axes[0].set_title("Front elevation")
        render_elevation(params, axes[0])

        # Parameter summary panel
        axes[1].axis("off")
        summary = "\n".join([
            f"Footprint:    {params.w} × {params.d} blocks",
            f"Aspect ratio: {params.aspect_ratio:.2f}",
            f"Wall height:  {params.wall_h} blocks",
            f"Foundation:   {params.foundation_h} blocks",
            f"Upper storey: {'yes (' + str(params.upper_h) + ' blocks)' if params.has_upper else 'no'}",
            f"Roof type:    {params.roof_type}",
            f"Chimney:      {'yes' if params.has_chimney else 'no'}",
            f"Porch:        {'yes' if params.has_porch else 'no'}",
            f"Extension:    {'yes' if params.has_extension else 'no'}",
            "",
            "Score guide:",
            "  0.1-0.3  wrong / ugly",
            "  0.4-0.6  acceptable",
            "  0.7-0.8  good",
            "  0.9-1.0  excellent",
            "",
            f"Scored so far: {scored}",
            f"Skipped:       {skipped}",
        ])
        axes[1].text(
            0.05, 0.95, summary,
            transform=axes[1].transAxes,
            fontsize=10, verticalalignment="top",
            fontfamily="monospace",
        )

        plt.tight_layout()

        # Key press handler
        result = {"score": None, "quit": False, "skip": False}

        def on_key(event, result=result):
            k = event.key
            if k in "123456789":
                result["score"] = int(k) / 10.0
                plt.close()
            elif k == "0":
                result["score"] = 1.0
                plt.close()
            elif k in ("s", "S"):
                result["skip"] = True
                plt.close()
            elif k in ("q", "Q"):
                result["quit"] = True
                plt.close()

        fig.canvas.mpl_connect("key_press_event", on_key)
        plt.show(block=True)

        if result["quit"]:
            print(f"\nQuitting. Saved {scored} samples to {out_path}")
            break

        if result["skip"]:
            skipped += 1
            continue

        if result["score"] is not None:
            row = {name: val for name, val in zip(
                HouseParams.feature_names(),
                params.to_feature_vector().tolist(),
            )}
            # Restore string roof_type for readability
            row["roof_type"] = params.roof_type
            row["score"]     = result["score"]
            writer.writerow(row)
            outfile.flush()
            scored += 1
            print(f"  [{i+1:3d}] {params.w}×{params.d} {params.roof_type:8s} "
                  f"upper={int(params.has_upper)} → score {result['score']:.1f}")

    outfile.close()
    print(f"\nDone. {scored} samples saved to {out_path}")
    print(f"Next: python train_scorer.py --data {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate house scoring training data.")
    parser.add_argument("--samples", type=int, default=80,
                        help="Number of houses to score (default: 80).")
    parser.add_argument("--out", type=str, default="data/house_labels.csv",
                        help="Output CSV path (default: data/house_labels.csv).")
    parser.add_argument("--resume", action="store_true",
                        help="Append to existing CSV instead of overwriting.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility.")
    args = parser.parse_args()

    run_labelling_session(
        n_samples=args.samples,
        out_path=Path(args.out),
        resume=args.resume,
        seed=args.seed,
    )