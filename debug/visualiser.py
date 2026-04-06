"""Debug visualisation — analysis maps and in-world markers."""
from __future__ import annotations

import matplotlib.pyplot as plt
from gdpc import Block, Editor

from data.analysis_results import WorldAnalysisResult
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
