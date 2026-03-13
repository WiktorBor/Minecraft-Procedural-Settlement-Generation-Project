"""Main entry point: World analysis and settlement generation."""

import random
import sys
import argparse
from pathlib import Path
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))

from gdpc import Editor
from generators.settlement_generator import SettlementGenerator
from data.configurations import SettlementConfig
from data.settlement_state import SettlementState

from analysis.world_analysis import WorldAnalyser
from utils.http_client import GDMCClient
from world_interface.terrain_loader import TerrainLoader

def plot_analysis(wa):
    # Absolute coordinates relative to build area
    x0, z0 = wa.best_area.x_from - wa.build_area.x_from, wa.best_area.z_from - wa.build_area.z_from
    x1, z1 = wa.best_area.x_to - wa.build_area.x_from, wa.best_area.z_to - wa.build_area.z_from

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
    im2 = axs[1,0].imshow(wa.water_proximity, cmap="Blues")
    axs[1,0].set_title("Water Proximity")
    plt.colorbar(im2, ax=axs[1,0])

    # Overall score
    im3 = axs[1,1].imshow(wa.scores, cmap="viridis")
    axs[1,1].set_title("Overall Score")
    plt.colorbar(im3, ax=axs[1,1])

    # Highlight best area on score map
    axs[1,1].add_patch(
        plt.Rectangle((z0, x0), z1-z0, x1-x0, edgecolor='red', facecolor='none', linewidth=2)
    )

    plt.tight_layout()
    plt.show()

def main():
    parser = argparse.ArgumentParser(
        description='Analyse world and Generate Minecraft settlements')
    parser.add_argument('--buildings', type=int, default=None,
                       help='Number of buildings (default: random 12-15 for village)')
    parser.add_argument('--visualize', action='store_true',
                       help='Show debug visualizations in Minecraft')
    
    args = parser.parse_args()
    
    num_buildings = args.buildings
    if num_buildings is None:
        num_buildings = random.randint(12, 15)
        print(f"\n Using random building count: {num_buildings}")
    
    print("\n" + "="*60)
    print("GDMC WORLD ANALYSIS AND SETTLEMENT GENERATOR")
    print("="*60)
    print("\nInitializing...")

    client = GDMCClient()

    if not client.check_connection():
        print("\n Could not connect to GDMC HTTP Interface.\nIs Minecraft running?")
        sys.exit(1)
    
    print("\n Connection OK. Using your current build area.")

    # Generate settlement
    print("\n Starting settlement generation...")

    try:
        editor = Editor(buffering=True)
        terrain_loader = TerrainLoader(client)
        analyser = WorldAnalyser(terrain_loader).prepare()
        plot_analysis(analyser)
        state = SettlementState()
        config = SettlementConfig()
        generator = SettlementGenerator(
            editor, analyser, state, config
        )  

        generator.generate(num_buildings=num_buildings)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Generation cancelled by user")
        return 1
        
    print("\n Settlement generation complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
