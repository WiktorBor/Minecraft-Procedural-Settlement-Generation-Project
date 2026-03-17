from analysis.world_analysis import WorldAnalyser
from planning.settlement.district_planner import DistrictPlanner
from world_interface.terrain_loader import TerrainLoader
from utils.http_client import GDMCClient

from data.configurations import TerrainConfig, SettlementConfig

import numpy as np
import matplotlib.pyplot as plt


def main():

    print("Starting district planner test...")

    # ----------------------------
    # World analysis
    # ----------------------------

    client = GDMCClient()
    terrain = TerrainLoader(client)

    terrain_config = TerrainConfig()

    analyser = WorldAnalyser(terrain, terrain_config)

    result = analyser.prepare()

    print("Best area:", result.best_area)
    print("Best area size:", result.best_area.width, result.best_area.depth)

    # ----------------------------
    # District planning
    # ----------------------------

    settlement_config = SettlementConfig()

    planner = DistrictPlanner(
        analysis=result,
        config=settlement_config,
        seed=42
    )

    districts = planner.generate()

    # ----------------------------
    # Diagnostics
    # ----------------------------

    print("\nDistrict count:", len(districts.district_list))

    for i, d in enumerate(districts.district_list):

        print(
            f"District {i}:",
            f"type={d.type}",
            f"x={d.x}",
            f"z={d.z}",
            f"w={d.width}",
            f"d={d.depth}",
        )

    print("\nDistrict map shape:", districts.map.shape)

    unique = np.unique(districts.map)

    print("District IDs present:", unique)

    print("\nSeed positions:")
    print(districts.seeds)

    plt.imshow(districts.map)
    plt.title("District Map")
    plt.colorbar()
    plt.show()


if __name__ == "__main__":
    main()