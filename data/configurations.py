from dataclasses import dataclass

@dataclass
class SettlementConfig:

    min_plot_distance: int = 12

    max_slope: float = 0.5
    max_roughness: float = 2

    min_water_distance: int = 4

@dataclass
class TerrainConfig:

    # surface detection
    surface_ignore_blocks = [
        "air",
        "_leaves",
        "_log",
        "_wood",
        "grass",
        "flower",
        "water",
        "kelp",
        "seagrass",
        "tall_seagrass",
        "vine"
    ]

    surface_scan_depth = 32
    chunk_size = 32

    radius = 5

    biome_weights = {
        "minecraft:plains": 1.0,
        "minecraft:forest": 0.8,
        "minecraft:savanna": 0.8,
        "minecraft:desert": 0.5,
        "minecraft:swamp": 0.2,
        "minecraft:ocean": 0.0
    }

    min_patch_size = 100