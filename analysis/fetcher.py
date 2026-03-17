from __future__ import annotations

import numpy as np
from data.build_area import BuildArea
from world_interface.terrain_loader import TerrainLoader


class WorldFetcher:
    """
    Fetches all raw world data needed for terrain analysis.
    """

    def __init__(self, terrain_loader: TerrainLoader) -> None:
        self.terrain = terrain_loader

    def fetch_build_area(self) -> BuildArea:
        """
        Return the active build area from the world interface.
        """
        return self.terrain.get_build_area()

    def fetch_heightmaps(
        self, build_area: BuildArea
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Fetch heightmaps for the full build area.

        Returns
        -------
        surface, ground, ocean_floor, plant_thickness
            All float32 arrays of shape (width, depth).
            plant_thickness = surface - ground (vegetation height proxy).
        """
        x, z = build_area.x_from, build_area.z_from
        w, d = build_area.width, build_area.depth

        surface     = np.asarray(self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING"),           dtype=np.float32)
        ground      = np.asarray(self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING_NO_PLANTS"), dtype=np.float32)
        ocean_floor = np.asarray(self.terrain.get_heightmap(x, z, w, d, "OCEAN_FLOOR"),               dtype=np.float32)

        return surface, ground, ocean_floor, surface - ground

    def fetch_biomes(self, build_area: BuildArea) -> np.ndarray:
        """
        Fetch biome data and resize to match the build area dimensions.

        The GDMC API may return plain strings or dicts like
        {"Name": "minecraft:plains", ...}.  This method normalises every
        element to a plain biome-name string before returning.

        Returns
        -------
        np.ndarray of dtype object and shape (width, depth) containing
        biome name strings, e.g. "minecraft:plains".
        """
        data = self.terrain.get_biomes(
            build_area.x_from,
            build_area.z_from,
            build_area.width,
            build_area.depth,
        )

        # Normalise all cells to plain biome name strings, handling both dict and string formats.
        def _to_name(cell) -> str:
            if isinstance(cell, dict):
                return str(cell.get("Name", cell.get("name", "minecraft:plains")))
            return str(cell)

        flat    = np.array([_to_name(c) for c in np.asarray(data).ravel()], dtype=object)
        data    = flat.reshape(np.asarray(data).shape)

        if data.ndim == 1:
            data = data.reshape((1, -1))

        # Over-tile then trim to exact target shape
        w, d   = build_area.width, build_area.depth
        reps_x = w // data.shape[0] + 1
        reps_z = d // data.shape[1] + 1
        data   = np.tile(data, (reps_x, reps_z))

        return data[:w, :d]