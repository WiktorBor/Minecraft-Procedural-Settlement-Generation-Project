"""Debug visualisation — analysis maps and in-world markers."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from gdpc import Block, Editor

from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Districts
from data.settlement_state import SettlementState


def plot_analysis(analysis: WorldAnalysisResult) -> None:
    """Display a 2×2 matplotlib grid of terrain analysis maps."""
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))

    im0 = axs[0, 0].imshow(analysis.heightmap_ground, cmap="terrain")
    axs[0, 0].set_title("Ground Heightmap")
    plt.colorbar(im0, ax=axs[0, 0])

    im1 = axs[0, 1].imshow(analysis.slope_map, cmap="magma")
    axs[0, 1].set_title("Slope Map")
    plt.colorbar(im1, ax=axs[0, 1])

    im2 = axs[1, 0].imshow(analysis.water_distances, cmap="Blues")
    axs[1, 0].set_title("Water Distance")
    plt.colorbar(im2, ax=axs[1, 0])

    im3 = axs[1, 1].imshow(analysis.scores, cmap="viridis")
    axs[1, 1].set_title("Overall Score")
    plt.colorbar(im3, ax=axs[1, 1])

    area = analysis.best_area
    axs[1, 1].add_patch(
        plt.Rectangle(
            (area.z_from, area.x_from),
            area.z_to - area.z_from,
            area.x_to - area.x_from,
            edgecolor="red", facecolor="none", linewidth=2,
        )
    )

    plt.tight_layout()
    plt.show()


_DISTRICT_COLOURS: dict[str, str] = {
    "residential": "#F4A460",   # sandy orange
    "farming":     "#7CFC00",   # lawn green
    "fishing":     "#00CED1",   # cyan
    "forest":      "#228B22",   # forest green
    "mining":      "#808080",   # gray
    "commercial":  "#FFD700",   # yellow
    "industrial":  "#8B4513",   # brown
    "decoration":  "#FF69B4",   # pink
}
_FALLBACK_COLOUR = "#9400D3"  # purple


def plot_districts(
    analysis: WorldAnalysisResult,
    districts: Districts,
    show: bool = True,
) -> None:
    """
    Render the district Voronoi map using matplotlib. No Minecraft required.

    Shows a coloured district map with district-centre markers and MST
    connectivity lines overlaid on a faint heightmap background.

    Call this after plan_districts() returns, before plan_roads().
    """
    from utils.mst import mst_edges

    area  = analysis.best_area
    dmap  = districts.map          # (W, D) int32
    hmap  = analysis.heightmap_ground
    W, D  = dmap.shape

    # Build an RGB image from the district map
    rgb = np.zeros((W, D, 3), dtype=np.float32)
    for idx, dtype in districts.types.items():
        hex_col = _DISTRICT_COLOURS.get(dtype.strip().lower(), _FALLBACK_COLOUR)
        r = int(hex_col[1:3], 16) / 255
        g = int(hex_col[3:5], 16) / 255
        b = int(hex_col[5:7], 16) / 255
        mask = dmap == idx
        rgb[mask, 0] = r
        rgb[mask, 1] = g
        rgb[mask, 2] = b

    fig, (ax_score, ax_dist) = plt.subplots(1, 2, figsize=(18, 8))

    # --- Left panel: score map with best-area outline ---
    scores     = analysis.scores
    im = ax_score.imshow(scores.T, cmap="viridis", origin="lower")
    plt.colorbar(im, ax=ax_score, fraction=0.046, pad=0.04)

    # Red rectangle for the best area (scores are in full-build-area index space)
    full_area  = analysis.build_area
    bx0 = area.x_from - full_area.x_from
    bz0 = area.z_from - full_area.z_from
    bx1 = area.x_to   - full_area.x_from
    bz1 = area.z_to   - full_area.z_from
    ax_score.add_patch(mpatches.Rectangle(
        (bz0, bx0), bz1 - bz0, bx1 - bx0,
        edgecolor="red", facecolor="none", linewidth=2, label="best area",
    ))
    ax_score.legend(fontsize=8)
    ax_score.set_title("Score Map")
    ax_score.set_xlabel("Z (index)")
    ax_score.set_ylabel("X (index)")

    # --- Right panel: district Voronoi map ---
    ax_dist.imshow(hmap.T, cmap="gray", alpha=0.3, origin="lower",
                   extent=[0, W, 0, D])
    ax_dist.imshow(rgb.transpose(1, 0, 2), alpha=0.7, origin="lower",
                   extent=[0, W, 0, D])

    centres = []
    for idx, district in enumerate(districts.district_list):
        li, lj = area.world_to_index(district.center_x, district.center_z)
        centres.append((li, lj))
        dtype = districts.types.get(idx, "?")
        ax_dist.plot(li, lj, "k^", markersize=8)
        ax_dist.annotate(f"{idx}:{dtype}", (li, lj), textcoords="offset points",
                         xytext=(4, 4), fontsize=7, color="black",
                         bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6))

    edges = mst_edges([(cx, cz) for cx, cz in centres])
    for u, v in edges:
        ax_dist.plot([centres[u][0], centres[v][0]],
                     [centres[u][1], centres[v][1]],
                     "k--", linewidth=1, alpha=0.6)

    patches = [
        mpatches.Patch(color=col, label=dtype)
        for dtype, col in _DISTRICT_COLOURS.items()
        if dtype in districts.types.values()
    ]
    ax_dist.legend(handles=patches, loc="upper right", fontsize=8)
    ax_dist.set_title("District Partitioning")
    ax_dist.set_xlabel("X (local index)")
    ax_dist.set_ylabel("Z (local index)")

    plt.tight_layout()
    if show:
        plt.show()
    return fig


def place_markers(
    editor: Editor,
    analysis: WorldAnalysisResult,
    state: SettlementState,
) -> None:
    """Place gold blocks at plot centres and red wool at district centres."""
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground

    for plot in state.plots:
        try:
            li, lj = area.world_to_index(int(plot.center_x), int(plot.center_z))
        except ValueError:
            continue
        y = int(heightmap[li, lj])
        editor.placeBlock(
            (int(plot.center_x), y + 1, int(plot.center_z)),
            Block("minecraft:gold_block"),
        )

    for district in state.districts.district_list:
        cx, cz = int(district.center_x), int(district.center_z)
        try:
            li, lj = area.world_to_index(cx, cz)
        except ValueError:
            continue
        y = int(heightmap[li, lj])
        editor.placeBlock((cx, y + 2, cz), Block("minecraft:red_wool"))

    editor.flushBuffer()
