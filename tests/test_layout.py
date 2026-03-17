from analysis.world_analysis import WorldAnalyser
from planning.settlement_planner import SettlementPlanner
from utils.http_client import GDMCClient
from world_interface.terrain_loader import TerrainLoader
from data.configurations import TerrainConfig, SettlementConfig
from gdpc import Editor, Block
from world_interface.road_placer import RoadBuilder
from world_interface.terrain_clearer import remove_sparse_top

def debug_render_plots(editor, state, analysis):

    ba = analysis.best_area

    x_from, z_from = ba.x_from, ba.z_from
    x_to, z_to = ba.x_to, ba.z_to

    outline_block = Block("yellow_wool")

    for z in (z_from, z_to):
        for x in range(x_from, x_to + 1):
            ix, iz = ba.world_to_index(x, z)
            y = analysis.heightmap_ground[ix, iz]
            editor.placeBlock((x, y + 1, z), outline_block)

    for x in (x_from+1, x_to-1):
        for z in range(z_from, z_to + 1):
            ix, iz = ba.world_to_index(x, z)
            y = analysis.heightmap_ground[ix, iz]
            editor.placeBlock((x, y + 1, z), outline_block)


    for plot in state.plots:
        print(f"Plot at ({plot.x}, {plot.z}), size ({plot.width}x{plot.depth})")

        x0 = plot.x
        z0 = plot.z
        x1 = x0 + plot.width
        z1 = z0 + plot.depth

        for x in range(x0, x1):
            for z in [z0, z1]:

                ix, iz = analysis.best_area.world_to_index(x, z)
                y = analysis.heightmap_ground[ix, iz]
                editor.placeBlock((x, y + 1, z), Block("blue_wool"))

        for z in range(z0, z1):
            for x in [x0, x1]:
                ix, iz = analysis.best_area.world_to_index(x, z)

                y = analysis.heightmap_ground[ix, iz]
                editor.placeBlock((x, y + 1, z), Block("red_wool"))

    editor.flushBuffer()

def main():

    print("Starting settlement pipeline test...")

    # Connect to Minecraft / GDPC
    editor = Editor(buffering=True)

    # --- WORLD ANALYSIS ---
    client = GDMCClient()
    terrain = TerrainLoader(client)
    terrain_config = TerrainConfig()

    analyser = WorldAnalyser(
        terrain_loader=terrain,
        configuration=terrain_config
    )

    analysis = analyser.prepare()

    print("✓ World analysis complete")
    print("Best build area:", analysis.best_area)

    remove_sparse_top(editor, analysis)

    # --- SETTLEMENT PLANNING ---
    settlement_config = SettlementConfig()

    planner = SettlementPlanner(
        analysis=analysis,
        config=settlement_config
    )

    state = planner.plan()
    road_builder = RoadBuilder(editor, analysis)
    road_builder.build(state.roads)

    print("\n✓ Settlement planning complete")

    print("\n--- SUMMARY ---")
    print("Districts:", len(state.districts.district_list))
    print("Road cells:", len(state.roads))
    print("Plots:", len(state.plots))

    debug_render_plots(editor, state, analysis)


if __name__ == "__main__":
    main()