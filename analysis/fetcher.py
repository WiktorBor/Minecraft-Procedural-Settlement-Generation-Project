from __future__ import annotations

import numpy as np

from data.build_area import BuildArea
from data.configurations import TerrainConfig
from utils.interfaces import TerrainLoaderProtocol


class WorldFetcher:
    """
    Fetches all raw world data needed for terrain analysis.

    Depends on TerrainLoaderProtocol so that analysis/ never imports the
    concrete world_interface implementation.
    """

    def __init__(self, terrain_loader: TerrainLoaderProtocol) -> None:
        self.terrain = terrain_loader

    def fetch_build_area(self) -> BuildArea:
        """Return the active build area from the world interface."""
        return self.terrain.get_build_area()

    def fetch_heightmaps(
        self,
        build_area: BuildArea,
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
        w, d = build_area.width,  build_area.depth

        surface     = np.asarray(
            self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING"),
            dtype=np.float32,
        )
        ground      = np.asarray(
            self.terrain.get_heightmap(x, z, w, d, "MOTION_BLOCKING_NO_PLANTS"),
            dtype=np.float32,
        )
        ocean_floor = np.asarray(
            self.terrain.get_heightmap(x, z, w, d, "OCEAN_FLOOR"),
            dtype=np.float32,
        )

        return surface, ground, ocean_floor, surface - ground

    def fetch_biomes(self, build_area: BuildArea) -> np.ndarray:
        """
        Fetch biome data and reshape to (width, depth).

        The GDMC API may return plain strings or dicts like
        {"Name": "minecraft:plains", ...}.  Every element is normalised to a
        plain biome-name string before returning.

        Returns
        -------
        np.ndarray of dtype object and shape (width, depth) containing
        biome name strings, e.g. "minecraft:plains".
        """
        raw = self.terrain.get_biomes(
            build_area.x_from,
            build_area.z_from,
            build_area.width,
            build_area.depth,
        )

        w, d = build_area.width, build_area.depth

        def _to_name(cell) -> str:
            if isinstance(cell, dict):
                return str(cell.get("Name", cell.get("name", "minecraft:plains")))
            return str(cell)

        raw_arr = np.asarray(raw)
        flat = np.array(
            [_to_name(c) for c in raw_arr.ravel()],
            dtype=object,
        )
        data = flat.reshape(raw_arr.shape)

        if data.ndim == 1:
            data = data.reshape((1, -1))

        # Tile to cover (w, d) then trim — handles API returning fewer cells
        # than the requested area (e.g. one biome value per chunk column).
        reps_x = w // data.shape[0] + 1
        reps_z = d // data.shape[1] + 1
        return np.tile(data, (reps_x, reps_z))[:w, :d]

    def fetch_surface_block_ids(
        self,
        best_area: BuildArea,
        heightmap_ground: np.ndarray,
        config: TerrainConfig,
    ) -> np.ndarray:
        """
        Fetch the top solid surface block ID for each cell in `best_area`.

        Scans downward from the ground heightmap, ignoring non-solid blocks
        (leaves, air, etc.) as defined by `config.surface_ignore_blocks`.

        Parameters
        ----------
        best_area : BuildArea
            The sub-area to scan (must be smaller than or equal to the full
            build area).
        heightmap_ground : np.ndarray
            2-D float array of shape (best_area.width, best_area.depth) giving
            the ground Y level for each cell.  Must already be sliced to
            `best_area` — do not pass the full-build-area heightmap here.
        config : TerrainConfig
            Provides `chunk_size` and `surface_ignore_blocks`.

        Returns
        -------
        np.ndarray of dtype object and shape (best_area.width, best_area.depth)
            Surface block ID string per cell (e.g. "minecraft:grass_block").
        """
        h_w, h_d = heightmap_ground.shape
        chunk_size = config.chunk_size
        surface_block_ids = np.full(
            heightmap_ground.shape,
            fill_value="minecraft:air",
            dtype=object,
        )

        for x in range(0, h_w, chunk_size):
            for z in range(0, h_d, chunk_size):
                dx = min(chunk_size, h_w - x)
                dz = min(chunk_size, h_d - z)

                chunk_hmap = heightmap_ground[x:x + dx, z:z + dz]
                y_max = int(np.max(chunk_hmap))
                # Scan from the lowest cell height so every block — including
                # lava pools that sit far below a hilltop in the same chunk —
                # is covered.  Without this, cells more than surface_scan_depth
                # below the chunk peak silently return "minecraft:air".
                y_min = max(0, int(np.min(chunk_hmap)) - 1)
                actual_depth = y_max - y_min

                if actual_depth <= 0:
                    continue

                world_x = best_area.x_from + x
                world_z = best_area.z_from + z

                raw_data = self.terrain.get_blocks(
                    world_x, y_min, world_z, dx, actual_depth, dz
                )
                grid = self._build_block_grid(
                    raw_data, dx, actual_depth, dz, world_x, y_min, world_z
                )
                surface_block_ids[x:x + dx, z:z + dz] = self._find_surface(
                    grid, config
                )

        return surface_block_ids

    def _build_block_grid(
        self,
        raw_data: list[dict],
        dx: int,
        dy: int,
        dz: int,
        offset_x: int,
        offset_y: int,
        offset_z: int,
    ) -> np.ndarray:
        """Convert raw block list into a 3-D (dx, dy, dz) string array."""
        grid = np.full((dx, dy, dz), fill_value="minecraft:air", dtype=object)
        for b in raw_data:
            lx = b["x"] - offset_x
            ly = b["y"] - offset_y
            lz = b["z"] - offset_z
            if 0 <= lx < dx and 0 <= ly < dy and 0 <= lz < dz:
                grid[lx, ly, lz] = b.get("id", "minecraft:air").lower()
        return grid

    def _find_surface(
        self,
        grid: np.ndarray,
        config: TerrainConfig,
    ) -> np.ndarray:
        """
        Return the top solid block ID per (x, z) column in `grid`.

        "Solid" means the block ID does not contain any substring from
        `config.surface_ignore_blocks`.

        Returns
        -------
        np.ndarray of dtype object and shape (dx, dz).
        """
        ignore_list = config.surface_ignore_blocks
        dx, dy, dz = grid.shape

        def is_ignored(block_id: str) -> bool:
            b_lower = str(block_id).lower()
            return any(key in b_lower for key in ignore_list)
        
        v_is_ignored = np.vectorize(is_ignored)
        valid = ~v_is_ignored(grid)

        valid_flipped = valid[:, ::-1, :]
        top_idx_flipped = np.argmax(valid_flipped, axis=1)
        has_valid = valid_flipped.any(axis=1)
        
        surface_y = np.where(
            has_valid,
            (dy - 1) - top_idx_flipped,
            0
        )

        xs = np.arange(dx)
        zs = np.arange(dz)

        surface_ids = grid[xs[:, None], surface_y, zs]
        return surface_ids