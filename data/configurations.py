from dataclasses import dataclass, field
from typing import Dict, List, Any
@dataclass
class SettlementConfig:
    """
    Settlement placement and planning configuration.
    All distances in blocks/grid cells."""

    min_plot_distance: int = 6
    min_plot_cluster_distance: int = 6
    max_plot_cluster_distance: int = 18
    min_water_distance: int = 3
    max_height_variation: int = 2
    max_slope: float = 0.6
    max_roughness: float = 2.0
    num_districts: int = 5
    road_width: int = 3
    radius: int = 6

    # District-specific rules
    district_type_rules = {
        "fishing": {"water_dist_max": 10},
        "farming": {"slope_max": 1.5, "roughness_max": 1.5, "probability": 0.6},
        "residential": {"slope_max": 0.8, "roughness_max": 1.0, "probability": 0.7},
        "forest": {}
    }

    plot_width = {
        "residential": 8,
        "farming": 12,
        "fishing": 6
    }

    plot_depth = {
        "residential": 8,
        "farming": 12,
        "fishing": 6
    }

    min_plot_size = {
        "residential": 6,
        "farming": 10,
        "fishing": 5
    }

@dataclass
class TerrainConfig:
    """
    Terrain analysis and procedural generation configuration.
    """

    # Blockes ignored when detecting surface
    surface_ignore_blocks:List[str] = field(default_factory=lambda: [
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
    ])

    surface_scan_depth: int = 32
    chunk_size: int = 32
    forest_scale: float = 5.0
    slope_scale: float = 3.0
    radius: int = 5
    max_slope: float = 0.6
    max_roughness: float = 2.0
    min_patch_size: int = 150
    top_building_score_percentile: float = 0.25

    # Biome weights for placement scoring
    biome_weights: Dict[str, float] = field(default_factory=lambda:{
        "minecraft:plains": 1.0,
        "minecraft:forest": 0.8,
        "minecraft:savanna": 0.7,
        "minecraft:desert": 0.5,
        "minecraft:swamp": 0.2,
        "minecraft:ocean": 0.0
    })

    # Block keywords for vegetation detection
    VEGETATION_BLOCK_KEYWORDS: List[str] = field(default_factory=lambda: [
        "log",
        "leaves",
        "vine",
        "sapling",
        "bamboo",
        "grass",
        "fern",
        "flower",
        "mushroom"
    ])