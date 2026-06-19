"""Updated training data generator for the new House system."""
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
    """2D front-elevation preview with door, windows, chimney, and porch."""
    plt.clf()
    ax = plt.gca()

    wall_color = '#8B6347' if params.structure_role == "cottage" else '#9E9E9E'
    roof_color = '#C0392B'

    # --- Ground line ---
    plt.plot([-0.5, params.w + 0.5], [0, 0], 'k-', lw=2)

    # --- Porch platform (if present) ---
    if params.has_porch:
        ax.add_patch(plt.Rectangle((-0.5, -0.2), params.w + 1, 0.2, color='#A0826D', zorder=2))

    # --- Walls ---
    ax.add_patch(plt.Rectangle((0, 0), params.w, params.wall_h,
                                facecolor=wall_color, edgecolor='#4A3728', linewidth=1.5, alpha=0.6, zorder=3))

    # --- Upper storey (if present) ---
    if params.has_upper:
        upper_h = params.wall_h * 0.6
        ax.add_patch(plt.Rectangle((0.5, params.wall_h), params.w - 1, upper_h,
                                    facecolor=wall_color, edgecolor='#4A3728', linewidth=1, alpha=0.4, zorder=3))

    # --- Door (centred, ground level) ---
    door_w, door_h = 0.8, 1.6
    door_x = (params.w - door_w) / 2
    ax.add_patch(plt.Rectangle((door_x, 0), door_w, door_h,
                                facecolor='#5D3A1A', edgecolor='#2C1A0E', linewidth=1, zorder=4))
    # door knob
    ax.add_patch(plt.Circle((door_x + door_w - 0.15, door_h / 2), 0.07,
                             color='#FFD700', zorder=5))

    # --- Windows (evenly spaced, avoiding the door column) ---
    win_w, win_h = 0.7, 0.7
    win_y = params.wall_h * 0.5
    # how many windows fit either side of the door
    n_windows = max(1, (params.w // 3) - 1)
    spacing = params.w / (n_windows + 1)
    for i in range(1, n_windows + 1):
        wx = i * spacing - win_w / 2
        # skip if overlapping door
        if abs(wx - door_x) < 1.0:
            continue
        ax.add_patch(plt.Rectangle((wx, win_y), win_w, win_h,
                                    facecolor='#AED6F1', edgecolor='#2C3E50', linewidth=1, zorder=4))
        # window cross
        ax.plot([wx, wx + win_w], [win_y + win_h / 2, win_y + win_h / 2], color='#2C3E50', lw=0.7, zorder=5)
        ax.plot([wx + win_w / 2, wx + win_w / 2], [win_y, win_y + win_h], color='#2C3E50', lw=0.7, zorder=5)

    # --- Roof ---
    roof_base = params.wall_h if not params.has_upper else params.wall_h + params.wall_h * 0.6
    if params.roof_type == "gabled":
        peak_h = 2.5
        xs = [0, params.w / 2, params.w, 0]
        ys = [roof_base, roof_base + peak_h, roof_base, roof_base]
        ax.fill(xs, ys, color=roof_color, alpha=0.75, zorder=3)
        ax.plot(xs, ys, color='#7B241C', lw=1.5, zorder=4)
    elif params.roof_type == "steep":
        peak_h = 4.0
        xs = [0, params.w / 2, params.w, 0]
        ys = [roof_base, roof_base + peak_h, roof_base, roof_base]
        ax.fill(xs, ys, color=roof_color, alpha=0.75, zorder=3)
        ax.plot(xs, ys, color='#7B241C', lw=1.5, zorder=4)
    else:  # cross — show as flat with slight raise
        peak_h = 2.0
        xs = [0, params.w / 2, params.w, 0]
        ys = [roof_base, roof_base + peak_h, roof_base, roof_base]
        ax.fill(xs, ys, color=roof_color, alpha=0.75, zorder=3)
        ax.plot(xs, ys, color='#7B241C', lw=1.5, zorder=4)

    # --- Chimney (if present) ---
    if params.has_chimney:
        chim_x = params.w * 0.75
        chim_base = roof_base + 1.2
        ax.add_patch(plt.Rectangle((chim_x, chim_base), 0.5, 1.2,
                                    facecolor='#784212', edgecolor='#4A2C0A', linewidth=1, zorder=5))

    # --- Labels ---
    extras = []
    if params.has_chimney: extras.append("chimney")
    if params.has_porch:   extras.append("porch")
    if params.has_upper:   extras.append("upper floor")
    extra_str = "  [" + ", ".join(extras) + "]" if extras else ""
    plt.title(
        f"{params.structure_role.upper()}  {params.w}w × {params.d}d × {params.wall_h}h  |  roof: {params.roof_type}{extra_str}",
        fontsize=10
    )
    plt.xlim(-1, params.w + 1)
    plt.ylim(-1, roof_base + 6)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    plt.draw()

def run_session(n_samples, out_path):
    # Ensure directories exist
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Column names must match house_labels.csv exactly
    fieldnames = ["w", "d", "wall_h", "role", "roof_type", "has_upper", "has_chimney", "has_porch", "aspect", "score"]
    file_exists = out_path.exists() and out_path.stat().st_size > 0

    with open(out_path, "a" if file_exists else "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        plt.ion()
        plt.show()
        for i in range(n_samples):
            p = sample_params()
            render_preview(p)
            val = input(f"[{i+1}/{n_samples}] Score 1-10 (or 'q' to quit): ")
            if val.lower() == 'q': break
            try:
                raw = float(val)
                # Accept either 1-10 or 0.0-1.0 input
                score = raw / 10.0 if raw > 1.0 else raw
                row = {
                    "w": p.w, "d": p.d, "wall_h": p.wall_h,
                    "role": p.structure_role, "roof_type": p.roof_type,
                    "has_upper": int(p.has_upper), "has_chimney": int(p.has_chimney),
                    "has_porch": int(p.has_porch), "aspect": p.aspect_ratio,
                    "score": round(score, 3)
                }
                writer.writerow(row)
                f.flush()
            except ValueError:
                print("  Invalid input, skipping.")
                continue

if __name__ == "__main__":
    run_session(50, Path("training/house_labels.csv"))