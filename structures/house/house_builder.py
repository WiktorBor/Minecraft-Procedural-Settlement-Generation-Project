"""Generates varied residential buildings."""
from __future__ import annotations


import random

from gdpc.editor import Editor

from world_interface.terrain_clearer import clear_area
from data.analysis_results import WorldAnalysisResult
from data.configurations import TerrainConfig
from data.settlement_entities import Plot
from data.biome_palettes import BiomePalette, get_biome_palette
from .components import (
    build_floor,
    build_walls,
    build_gabled_roof,
    build_flat_roof,
    add_windows,
    add_door,
    add_chimney,
)

_WALL_HEIGHT = 5  # default wall height in blocks


class HouseBuilder:

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        terrain_config: TerrainConfig,
        palette: BiomePalette | None = None,
    ) -> None:
        self.editor         = editor
        self.analysis       = analysis
        self.terrain_config = terrain_config
        self.palette        = palette if palette is not None else get_biome_palette()

    def build_house(self, plot: Plot, decisions: dict) -> None:
        """
        Build a house at the given plot using the provided decisions.

        Wraps all block placements in a buffer so the entire house is
        sent to the server in a single HTTP request.

        Args:
            plot: The plot to build on.
            decisions: dict from HouseAgent.decide(); must have 'build' key.
        """
        if not decisions.get("build", True):
            return

        x, z        = plot.x, plot.z
        y           = plot.y
        w, d        = plot.width, plot.depth
        wall_height = _WALL_HEIGHT
        roof_y      = y + wall_height

        clear_area(
            editor=self.editor,
            analysis=self.analysis,
            plot=plot,
            config=self.terrain_config,
        )

        # Placements are batched via Editor(buffering=True) set in main.py
        build_floor(self.editor, x, y, z, w, d, self.palette["floor"])
        build_walls(self.editor, x, y, z, w, wall_height, d, self.palette["wall"])
        build_gabled_roof(
            self.editor, x, roof_y, z, w, d,
            material=self.palette["roof"],
        )
        add_windows(self.editor, x, y, z, w, d, "minecraft:glass_pane")
        add_door(self.editor, x, y, z, w, "minecraft:oak_door")
        add_chimney(self.editor, x, y + 1, z, w, d, wall_height + 3, self.palette["foundation"])