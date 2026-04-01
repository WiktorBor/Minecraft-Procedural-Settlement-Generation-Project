from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


# ---------------------------------------------------------------------------
# District rule schema
# ---------------------------------------------------------------------------

class DistrictRule(TypedDict, total=False):
    """
    Terrain constraints and placement probability for a district type.
    All keys are optional — missing keys mean no constraint applies.
    """
    water_dist_max: float  # maximum distance to water (cells)
    slope_max:      float  # maximum terrain slope
    roughness_max:  float  # maximum terrain roughness
    probability:    float  # relative placement probability [0, 1]


# ---------------------------------------------------------------------------
# Settlement configuration
# ---------------------------------------------------------------------------

@dataclass
class SettlementConfig:
    """
    Settlement placement and planning configuration.
    All distances in blocks / grid cells unless noted otherwise.
    """

    # Plot spacing
    min_plot_distance:         int   = 6
    min_plot_cluster_distance: int   = 4
    max_plot_cluster_distance: int   = 30

    # Terrain thresholds for plot validation
    min_water_distance:  int   = 1
    max_height_variation: int  = 6
    max_slope:           float = 5.0
    max_roughness:       float = 8.0

    # District generation
    num_districts:               int = 5
    target_district_size:        int = 1000  # target cells per district
    min_structures_per_district: int = 2

    # Road
    road_width: int = 3
    radius:     int = 6

    # Per-district terrain rules
    district_type_rules: dict[str, DistrictRule] = field(
        default_factory=lambda: {
            "fishing":     {"water_dist_max": 10},
            "farming":     {"slope_max": 3.0, "roughness_max": 8.0, "probability": 0.6},
            "residential": {"slope_max": 2.5, "roughness_max": 6.0, "probability": 0.7},
            "forest":      {},
        }
    )

    # Plot dimensions per district type (blocks)
    plot_width: dict[str, int] = field(
        default_factory=lambda: {
            "residential": 8,
            "farming":     12,
            "fishing":     6,
            "forest":      8,
        }
    )
    plot_depth: dict[str, int] = field(
        default_factory=lambda: {
            "residential": 8,
            "farming":     12,
            "fishing":     6,
            "forest":      8,
        }
    )
    min_plot_size: dict[str, int] = field(
        default_factory=lambda: {
            "residential": 6,
            "farming":     10,
            "fishing":     5,
            "forest":      6,
        }
    )

    # Structure-type ratios (best-effort; fishing redistributed if no water)
    ratio_residential: float = 0.60
    ratio_functional:  float = 0.20
    ratio_fishing:     float = 0.10
    ratio_decoration:  float = 0.10

    # Fortification
    tower_height:    int = 8   # height of corner towers above ground
    tower_width:     int = 5   # square footprint of corner towers
    wall_height:     int = 5   # height of crenellated walls
    wall_thickness:  int = 2   # wall block depth
    gate_width:      int = 4   # gate opening width


# ---------------------------------------------------------------------------
# Terrain analysis configuration
# ---------------------------------------------------------------------------

@dataclass
class TerrainConfig:
    """
    Terrain analysis and procedural generation configuration.
    """

    # Substrings matched against block IDs to skip non-solid surface blocks
    surface_ignore_blocks: list[str] = field(default_factory=lambda: [
        "air", "_leaves", "_log", "_wood",
        "grass", "flower", "water",
        "kelp", "seagrass", "tall_seagrass", "vine",
    ])

    surface_scan_depth:            int   = 32
    chunk_size:                    int   = 32
    forest_scale:                  float = 5.0
    slope_scale:                   float = 3.0
    radius:                        int   = 5
    # Slope / roughness thresholds for the patch selector (normalised values,
    # not block counts). 0.6 / 2.0 was too strict — gentle hills near water
    # failed on a second run after structures slightly raised roughness.
    # 1.2 / 3.5 accepts any terrain a settlement can reasonably sit on.
    max_slope:                     float = 1.2
    max_roughness:                 float = 3.5

    # Minimum contiguous valid cells.  64 guarantees at least an 8x8 footprint.
    min_patch_size:                int   = 64

    top_building_score_percentile: float = 0.40

    # Water proximity penalty — cells within this many blocks of water get
    # their score multiplied by water_proximity_score_mult before region
    # selection, preventing flat shoreline from beating inland land.
    water_proximity_penalty_cells: int   = 3
    water_proximity_score_mult:    float = 0.5

    # Minimum best-area dimensions — PatchSelector expands to meet these
    min_best_area_width: int = 64
    min_best_area_depth: int = 64

    # Cap the area actually fetched and analysed.  Very large build areas
    # (e.g. 1001×1001) cause heightmap requests to time out; we only need a
    # reasonable sub-area centred on the build area to find a good build site.
    max_analysis_size: int = 256

    # Biome suitability weights [0, 1] for placement scoring
    biome_weights: dict[str, float] = field(default_factory=lambda: {
        "minecraft:plains":  1.0,
        "minecraft:forest":  0.8,
        "minecraft:savanna": 0.7,
        "minecraft:desert":  0.5,
        "minecraft:swamp":   0.2,
        "minecraft:ocean":   0.0,
    })

    # Block name substrings used to detect vegetation during analysis
    vegetation_block_keywords: list[str] = field(default_factory=lambda: [
        "log", "leaves", "vine", "sapling",
        "bamboo", "grass", "fern", "flower", "mushroom",
    ])