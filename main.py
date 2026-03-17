"""Main entry point: World analysis, settlement planning, and structure generation."""

import random
import sys
import argparse
from pathlib import Path
import matplotlib.pyplot as plt

from gdpc import Editor, Block
from analysis.world_analysis import WorldAnalyser
from utils.http_client import GDMCClient
from world_interface.terrain_loader import TerrainLoader
from world_interface.road_placer import RoadBuilder
from data.configurations import TerrainConfig, SettlementConfig
from data.settlement_state import SettlementState
from generators.settlement_generator import SettlementGenerator

# ----------------------------
# Optional debug visualization of analysis
# ----------------------------
def plot_analysis(wa):
    # Coordinates relative to build area
    x0 = wa.best_area.x_from 
    z0 = wa.best_area.z_from 
    x1 = wa.best_area.x_to 
    z1 = wa.best_area.z_to 

    fig, axs = plt.subplots(2, 2, figsize=(12, 10))

    # Ground height
    im0 = axs[0,0].imshow(wa.heightmap_ground, cmap="terrain")
    axs[0,0].set_title("Ground Heightmap")
    plt.colorbar(im0, ax=axs[0,0])

    # Slope map
    im1 = axs[0,1].imshow(wa.slope_map, cmap="magma")
    axs[0,1].set_title("Slope Map")
    plt.colorbar(im1, ax=axs[0,1])

    # Water proximity
    im2 = axs[1,0].imshow(wa.water_distances, cmap="Blues")
    axs[1,0].set_title("Water Distance")
    plt.colorbar(im2, ax=axs[1,0])

    # Overall terrain score
    im3 = axs[1,1].imshow(wa.scores, cmap="viridis")
    axs[1,1].set_title("Overall Score")
    plt.colorbar(im3, ax=axs[1,1])

    # Highlight best area
    axs[1,1].add_patch(
        plt.Rectangle((z0, x0), z1 - z0, x1 - x0,
                      edgecolor='red', facecolor='none', linewidth=2)
    )

    plt.tight_layout()
    plt.show()


# ----------------------------
# Main generation pipeline
# ----------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Analyse world and generate Minecraft settlements'
    )
    parser.add_argument('--buildings', type=int, default=None,
                        help='Number of buildings (default: random 12-15 for village)')
    parser.add_argument('--visualize', action='store_true',
                        help='Show debug visualization in Minecraft')

    args = parser.parse_args()

    # Decide number of buildings
    num_buildings = args.buildings or random.randint(12, 15)
    print(f"\nUsing {num_buildings} buildings for this village.")

    print("\n" + "="*60)
    print("GDMC WORLD ANALYSIS AND SETTLEMENT GENERATOR")
    print("="*60)

    # Connect to GDMC
    client = GDMCClient()
    if not client.check_connection():
        print("\nCould not connect to GDMC HTTP Interface. Is Minecraft running?")
        sys.exit(1)

    print("\nConnection OK. Using current build area.")

    try:
        # ----------------------------
        # Editor and Terrain
        # ----------------------------
        editor = Editor(buffering=True)
        terrain_loader = TerrainLoader(client)
        terrain_config = TerrainConfig()

        # ----------------------------
        # World analysis
        # ----------------------------
        analyser = WorldAnalyser(
            terrain_loader=terrain_loader,
            configuration=terrain_config
        )
        analysis_result = analyser.prepare()
        print("✓ World analysis complete")
        print("Best build area:", analysis_result.best_area)

        # Optional: visualize terrain maps
        plot_analysis(analysis_result)

        # ----------------------------
        # Settlement planning
        # ----------------------------
        settlement_config = SettlementConfig()

        generator = SettlementGenerator(
            editor=editor,
            analyser=analysis_result,
            config=settlement_config
        )

        print("\nGenerating settlement...")
        generator.generate(num_buildings=num_buildings)  # builds roads, plots, and houses
        print("\n✓ Settlement generation complete")

        # Optional: visualize plots and district centers in Minecraft
        if args.visualize:
            area = analysis_result.best_area
            for plot in generator.state.plots:
                x_center, z_center = area.world_to_index(plot.x + plot.width, plot.z + plot.depth)
                x_center //= 2
                z_center //= 2
                y = analysis_result.heightmap_ground[x_center, z_center]
                editor.placeBlock((x_center, y + 1, z_center), Block("gold_block"))  # plot center marker

            for district in generator.state.districts.district_list:
                x, z = district.center
                x_local, z_local = area.world_to_index(x, z)
                y = analysis_result.heightmap_ground[x_local, z_local]
                editor.placeBlock((x, y + 2, z), Block("red_wool"))  # district center
            
            road_builder = RoadBuilder(editor, analysis_result)
            road_builder.build(generator.state.roads)
            editor.flushBuffer()

        # ----------------------------
        # Summary
        # ----------------------------
        print("\n--- SETTLEMENT SUMMARY ---")
        print("Districts:", len(generator.state.districts.district_list))
        print("Road cells:", len(generator.state.roads))
        print("Plots:", len(generator.state.plots))
        print("Buildings:", len(generator.state.buildings))

    except KeyboardInterrupt:
        print("\n⚠ Generation cancelled by user")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())