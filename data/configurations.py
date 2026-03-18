from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


# ---------------------------------------------------------------------------
# Typed structures for district rules
# ---------------------------------------------------------------------------

class DistrictRule(TypedDict, total=False):
    """
    Terrain constraints and placement probability for a district type.
    All keys are optional — missing keys mean "no constraint".
    """
    water_dist_max: float   # maximum distance to water (cells)
    slope_max:      float   # maximum terrain slope
    roughness_max:  float   # maximum terrain roughness
    probability:    float   # relative placement probability [0, 1]


# ---------------------------------------------------------------------------
# Settlement configuration
# ---------------------------------------------------------------------------

@dataclass
class SettlementConfig:
    """
    Settlement placement and planning configuration.
    All distances in blocks / grid cells.
    """

    min_plot_distance:         int   = 6
    min_plot_cluster_distance: int   = 6
    max_plot_cluster_distance: int   = 18
    min_water_distance:        int   = 3
    max_height_variation:      int   = 4   # raised: allow gentle slopes within a plot
    max_slope:                 float = 2.0 # raised: np.gradient slope, 0.6 was near-flat only
    max_roughness:             float = 6.0 # raised: local height range within radius
    num_districts:             int   = 5
    road_width:                int   = 3
    radius:                    int   = 6

    # District-specific terrain constraints and placement rules.
    # Use field(default_factory=...) so each instance gets its own dict.
    district_type_rules: dict[str, DistrictRule] = field(
        default_factory=lambda: {
            "fishing":     {"water_dist_max": 10},
            "farming":     {"slope_max": 3.0, "roughness_max": 8.0, "probability": 0.6},
            "residential": {"slope_max": 2.5, "roughness_max": 6.0, "probability": 0.7},
            "forest":      {},
        }
    )

    # Plot dimensions per district type (width and depth in blocks).
    # Separated in case non-square plots are needed in future.
    plot_width: dict[str, int] = field(
        default_factory=lambda: {
            "residential": 8,
            "farming":     12,
            "fishing":     6,
        }
    )

    plot_depth: dict[str, int] = field(
        default_factory=lambda: {
            "residential": 8,
            "farming":     12,
            "fishing":     6,
        }
    )

    min_plot_size: dict[str, int] = field(
        default_factory=lambda: {
            "residential": 6,
            "farming":     10,
            "fishing":     5,
        }
    )

    # Target structure-type ratios (best-effort, not guaranteed).
    # If no water access, fishing share is redistributed equally to others.
    ratio_residential:  float = 0.60
    ratio_functional:   float = 0.20
    ratio_fishing:      float = 0.10
    ratio_decoration:   float = 0.10

    # Fortification settings
    tower_height:       int   = 8    # height of corner towers (above ground)
    tower_width:        int   = 5    # footprint (square) of corner towers
    wall_height:        int   = 5    # height of connecting crenellated walls
    wall_thickness:     int   = 2    # wall block thickness
    gate_width:         int   = 4    # opening width of the settlement gate


# ---------------------------------------------------------------------------
# Terrain analysis configuration
# ---------------------------------------------------------------------------

@dataclass
class TerrainConfig:
    """
    Terrain analysis and procedural generation configuration.
    """

    # Blocks ignored when detecting the surface layer.
    surface_ignore_blocks: list[str] = field(default_factory=lambda: [
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
        "vine",
    ])

    surface_scan_depth:           int   = 32
    chunk_size:                   int   = 32
    forest_scale:                 float = 5.0
    slope_scale:                  float = 3.0
    radius:                       int   = 5
    max_slope:                    float = 0.6
    max_roughness:                float = 2.0
    min_patch_size:               int   = 150
    top_building_score_percentile: float = 0.25

    # Minimum dimensions (in blocks) for the selected best area.
    # PatchSelector expands the bounding box to meet these if the
    # natural best patch is smaller.
    min_best_area_width:  int = 64
    min_best_area_depth:  int = 64

    # Biome suitability weights for placement scoring [0, 1].
    biome_weights: dict[str, float] = field(default_factory=lambda: {
        "minecraft:plains":  1.0,
        "minecraft:forest":  0.8,
        "minecraft:savanna": 0.7,
        "minecraft:desert":  0.5,
        "minecraft:swamp":   0.2,
        "minecraft:ocean":   0.0,
    })

    # Block name substrings used to detect vegetation during analysis.
    vegetation_block_keywords: list[str] = field(default_factory=lambda: [
        "log",
        "leaves",
        "vine",
        "sapling",
        "bamboo",
        "grass",
        "fern",
        "flower",
        "mushroom",
    ])