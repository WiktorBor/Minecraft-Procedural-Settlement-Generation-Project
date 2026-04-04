"""Main entry point: world analysis, settlement planning, and structure generation."""
from __future__ import annotations


import argparse
import logging
import sys

import matplotlib.pyplot as plt
from gdpc import Block, Editor

from analysis.world_analysis import WorldAnalyser
from data.biome_palettes import get_biome_palette
from data.configurations import SettlementConfig, TerrainConfig
from data.settlement_state import SettlementState
from generators.settlement_generator import SettlementGenerator
from utils.http_client import GDMCClient
from world_interface.road_placer import RoadBuilder
from world_interface.terrain_loader import TerrainLoader

# ---------------------------------------------------------------------------
# Logging — configure once at entry point; all modules use getLogger(__name__)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("planning.settlement.plot_planner").setLevel(logging.DEBUG)
logging.getLogger("generators.settlement_generator").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Debug visualisation
# ---------------------------------------------------------------------------

def plot_analysis(wa) -> None:
    """Display a 2×2 matplotlib grid of terrain analysis maps."""
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))

    im0 = axs[0, 0].imshow(wa.heightmap_ground,  cmap="terrain")
    axs[0, 0].set_title("Ground Heightmap")
    plt.colorbar(im0, ax=axs[0, 0])

    im1 = axs[0, 1].imshow(wa.slope_map,          cmap="magma")
    axs[0, 1].set_title("Slope Map")
    plt.colorbar(im1, ax=axs[0, 1])

    im2 = axs[1, 0].imshow(wa.water_distances,    cmap="Blues")
    axs[1, 0].set_title("Water Distance")
    plt.colorbar(im2, ax=axs[1, 0])

    im3 = axs[1, 1].imshow(wa.scores,             cmap="viridis")
    axs[1, 1].set_title("Overall Score")
    plt.colorbar(im3, ax=axs[1, 1])

    x0 = wa.best_area.x_from
    z0 = wa.best_area.z_from
    x1 = wa.best_area.x_to
    z1 = wa.best_area.z_to
    axs[1, 1].add_patch(
        plt.Rectangle(
            (z0, x0), z1 - z0, x1 - x0,
            edgecolor="red", facecolor="none", linewidth=2,
        )
    )

    plt.tight_layout()
    plt.show()


def visualize_in_world(editor: Editor, analysis, state: SettlementState) -> None:
    """Place debug markers in Minecraft for plots, district centres, and roads."""
    area      = analysis.best_area
    heightmap = analysis.heightmap_ground

    # Gold block at each plot centre
    for plot in state.plots:
        try:
            li, lj = area.world_to_index(int(plot.center_x), int(plot.center_z))
        except ValueError:
            continue
        y = int(heightmap[li, lj])
        editor.placeBlock((int(plot.center_x), y + 1, int(plot.center_z)),
                          Block("minecraft:gold_block"))

    # Red wool at each district centre
    for district in state.districts.district_list:
        cx, cz = int(district.center_x), int(district.center_z)
        try:
            li, lj = area.world_to_index(cx, cz)
        except ValueError:
            continue
        y = int(heightmap[li, lj])
        editor.placeBlock((cx, y + 2, cz), Block("minecraft:red_wool"))

    # Roads
    palette      = get_biome_palette()
    road_builder = RoadBuilder(editor, analysis, palette)
    road_builder.build(state.roads)

    editor.flushBuffer()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse world and generate a Minecraft settlement."
    )
    parser.add_argument(
        "--buildings", type=int, default=None,
        help="Cap the number of buildings to place (default: build all plots).",
    )
    parser.add_argument(
        "--visualize", action="store_true",
        help="Show matplotlib analysis plots and place debug markers in-world.",
    )
    args = parser.parse_args()

    num_buildings = args.buildings
    if num_buildings is not None:
        logger.info("Capping settlement at %d buildings.", num_buildings)
    else:
        logger.info("Building on all available plots.")

    # --- connect ---
    client = GDMCClient()
    if not client.check_connection():
        logger.error("Could not connect to GDMC HTTP Interface. Is Minecraft running?")
        return 1

    logger.info("Connection OK. Using current build area.")

    try:
        editor         = Editor(buffering=True)
        terrain_config = TerrainConfig()
        terrain_loader = TerrainLoader(client)

        # --- world analysis ---
        logger.info("Analysing world...")
        analyser        = WorldAnalyser(terrain_loader=terrain_loader, configuration=terrain_config)
        analysis_result = analyser.prepare()
        logger.info("World analysis complete. Best area: %s", analysis_result.best_area)

        if args.visualize:
            plot_analysis(analysis_result)

        # --- settlement generation ---
        settlement_config = SettlementConfig()
        palette           = get_biome_palette()   # default plains; extend with biome detection later

        generator = SettlementGenerator(
            editor=editor,
            analysis=analysis_result,
            settlement_config=settlement_config,
            terrain_config=terrain_config,
            palette=palette,
            terrain_loader=terrain_loader,
        )

        state = generator.generate(num_buildings=num_buildings)
        logger.info("Settlement generation complete.")

        # --- optional in-world debug markers ---
        if args.visualize:
            visualize_in_world(editor, analysis_result, state)

        # --- summary ---
        logger.info("--- SETTLEMENT SUMMARY ---")
        logger.info("  Districts : %d", len(state.districts.district_list))
        logger.info("  Road cells: %d", state.road_cell_count)
        logger.info("  Plots     : %d", state.plot_count)
        logger.info("  Buildings : %d", state.building_count)

    except KeyboardInterrupt:
        logger.warning("Generation cancelled by user.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())