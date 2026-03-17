from analysis.world_analysis import WorldAnalyser
from planning.settlement.district_planner import DistrictPlanner
from planning.infrastructure.road_planner import RoadPlanner

from world_interface.terrain_loader import TerrainLoader
from world_interface.road_placer import RoadBuilder

from utils.http_client import GDMCClient

from data.settlement_state import SettlementState
from data.configurations import TerrainConfig, SettlementConfig

from gdpc import Editor, Block


# --------------------------------------------------
# Color palette for districts
# --------------------------------------------------

DISTRICT_COLORS = [
    "blue",
    "green",
    "yellow",
    "purple",
    "cyan",
    "orange",
    "lime",
    "pink",
    "light_blue",
    "magenta"
]


# --------------------------------------------------
# Draw district border
# --------------------------------------------------

def outline_rect(editor, x, z, width, depth, heightmap, color):

    block = Block(f"{color}_wool")

    for dx in range(width):

        y1 = int(heightmap[x + dx, z])
        y2 = int(heightmap[x + dx, z + depth - 1])

        editor.placeBlock((x + dx, y1 + 1, z), block)
        editor.placeBlock((x + dx, y2 + 1, z + depth - 1), block)

    for dz in range(depth):

        y1 = int(heightmap[x, z + dz])
        y2 = int(heightmap[x + width - 1, z + dz])

        editor.placeBlock((x, y1 + 1, z + dz), block)
        editor.placeBlock((x + width - 1, y2 + 1, z + dz), block)


# --------------------------------------------------
# Fill district area
# --------------------------------------------------

def fill_district(editor, district_id, districts_map, heightmap, build_area, origin_x, origin_z, color):

    carpet = Block(f"{color}_carpet")

    width, depth = districts_map.shape

    for dx in range(width):
        for dz in range(depth):

            if districts_map[dx, dz] == district_id:

                world_x = build_area.x_from + dx
                world_z = build_area.z_from + dz

                local_x = world_x - origin_x
                local_z = world_z - origin_z

                y = int(heightmap[local_x, local_z])

                editor.placeBlock((world_x, y + 1, world_z), carpet)

# --------------------------------------------------
# Place district center marker
# --------------------------------------------------

def place_district_center(editor, district, heightmap):

    cx, cz = district.center

    cx = int(cx)
    cz = int(cz)

    y = int(heightmap[cx, cz])

    editor.placeBlock((cx, y + 2, cz), Block("gold_block"))


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Starting settlement test...")

    client = GDMCClient()
    editor = Editor(buffering=True)

    terrain = TerrainLoader(client)

    # ----------------------------
    # World analysis
    # ----------------------------

    terrain_config = TerrainConfig()
    analyser = WorldAnalyser(terrain, terrain_config)

    result = analyser.prepare()

    heightmap = result.heightmap_ground
    best_area = result.best_area

    print("Heightmap shape:", result.heightmap_ground.shape)
    print ("Build area:", result.build_area)
    print("Best area:", best_area)

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

    print("Districts generated:", len(districts.district_list))

    # ----------------------------
    # Visualize districts
    # ----------------------------

    for i, district in enumerate(districts.district_list):

        color = DISTRICT_COLORS[i % len(DISTRICT_COLORS)]

        fill_district(
            editor,
            i,
            districts.map,
            heightmap,
            best_area,
            result.build_area.x_from,
            result.build_area.z_from,
            color
        )

        outline_rect(
            editor,
            district.x,
            district.z,
            district.width,
            district.depth,
            heightmap,
            color
        )

        place_district_center(editor, district, heightmap)

    # ----------------------------
    # Draw best build area
    # ----------------------------

    outline_rect(
        editor,
        best_area.x_from,
        best_area.z_from,
        best_area.width,
        best_area.depth,
        heightmap,
        "red"
    )

    editor.flushBuffer()

    print("District visualization complete.")

    # ----------------------------
    # Road planning
    # ----------------------------

    state = SettlementState()
    state.districts = districts.district_list

    road_planner = RoadPlanner(result, state)
    road_planner.generate()

    print("Roads generated:", len(state.roads))

    builder = RoadBuilder(editor, result)
    builder.build(state.roads)


if __name__ == "__main__":
    main()