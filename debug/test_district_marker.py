import logging
import numpy as np
from gdpc import Editor

# Project imports
from data.settlement_entities import Districts, District
from data.analysis_results import WorldAnalysisResult, BuildArea
from palette.palette_system import get_biome_palette
from structures.base.build_context import BuildContext
from world_interface.block_buffer import BlockBuffer
from structures.district_structures.district_marker import DistrictMarker
from world_interface.structure_placer import StructurePlacer

# Set up logging to track placement choices (Fountain vs Well)
logging.basicConfig(level=logging.INFO)

def test_markers():
    """
    Test script to verify DistrictMarker writes to the shared BuildContext
    and randomly chooses between fountains and wells.
    """
    editor = Editor(buffering=True)
    
    # 1. Mock Build Area (3D Box: x1, y1, z1, x2, y2, z2)
    # This creates a 100x100 area at y=0 to 255
    area = BuildArea(0, 0, 0, 100, 255, 100) 
    shape = (101, 101) # Indices for a 100x100 world coordinate range

    # 2. Mock ALL 9 required positional arguments for WorldAnalysisResult
    mock_analysis_data = {
        "surface_blocks":      np.full(shape, "minecraft:grass_block"),
        "heightmap_ground":    np.full(shape, 70),
        "heightmap_surface":   np.full(shape, 70),
        "heightmap_ocean_floor": np.full(shape, 60),
        "roughness_map":       np.zeros(shape),
        "slope_map":           np.zeros(shape),
        "water_mask":          np.zeros(shape),
        "biomes":              np.full(shape, "minecraft:plains"),
        "scores":              np.ones(shape)
    }
    analysis = WorldAnalysisResult(area, **mock_analysis_data)

    # 3. Mock Districts
    # District uses (x, z, width, depth) from RectangularArea
    # We place two small districts to act as centers for markers
    district_list = [
        District(x=15, z=15, width=10, depth=10), # Center ~ (20, 20)
        District(x=45, z=45, width=10, depth=10)  # Center ~ (50, 50)
    ]
    
    # Satisfy Districts __init__: map, types, seeds, voronoi
    district_map = np.zeros(shape, dtype=int)
    districts = Districts(
        map=district_map,
        types={0: "residential", 1: "fishing"},
        seeds=np.array([[20, 20], [50, 50]]),
        voronoi=None, # Pass None as it's not used by marker building logic
        district_list=district_list
    )

    # 4. Initialize the Shared BuildContext
    # This matches the pattern in SettlementGenerator.generate()
    palette = get_biome_palette("medieval")
    master_buffer = BlockBuffer()
    ctx = BuildContext(buffer=master_buffer, palette=palette)

    # 5. Run the Test
    print("\n--- Starting District Marker Test ---")
    marker_manager = DistrictMarker(analysis=analysis, ctx=ctx)
    
    # DistrictMarker now writes directly to master_buffer via ctx
    taken_cells = marker_manager.build(districts)

    # 6. Output Results
    print(f"Blocks generated in master buffer: {len(master_buffer)}")
    print(f"Total footprint marked 'taken':    {len(taken_cells)} cells")

    if len(master_buffer) > 0:
        print("RESULT: SUCCESS. Decoration blocks were added to the global context.")

        StructurePlacer(editor).place(master_buffer)
        editor.flushBuffer()
    else:
        print("RESULT: FAILED. No blocks were generated.")

if __name__ == "__main__":
    test_markers()