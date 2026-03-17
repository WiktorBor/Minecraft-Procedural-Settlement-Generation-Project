import numpy as np
from typing import Any
from data.build_area import BuildArea
from utils.http_client import GDMCClient
class TerrainLoader:
    """
    Loads terrain data from a GDMC server via the client interface.
    All coordinates are in world space.
    """
    def __init__(self, client: GDMCClient):
        self.client = client

    def get_build_area(self) -> BuildArea:
        """
        Fetch the build area from the server.
        Raises SystemExit if no build area is set.
        """
        if not self.client.check_build_area():
            raise RuntimeError(
                "\n No build area set. Set it in-game first, e.g.:\n"
                "   /buildarea set ~ ~ ~ ~199 ~ ~199   (200x200 from your position) \n"
                "   Or: /buildarea set x1 y1 z1 x2 y2 z2")
        
        data = self.client.get("/buildarea")
        return BuildArea(
            x_from=data["xFrom"],
            y_from=data["yFrom"],
            z_from=data["zFrom"],
            x_to=data["xTo"],
            y_to=data["yTo"],
            z_to=data["zTo"]
        )

    def get_heightmap(self, x, z, width, depth, heightmap_type) -> np.ndarray:
        """
        Fetch a 2D heightmap of given type.
        Returns:
            np.ndarray of shape [width, depth], indexed by [x, z]."""
        try:
            data = self.client.get("/heightmap", {
                "x": x,
                "z": z,
                "dx": width,
                "dz": depth,
                "type": heightmap_type
            })
        except Exception as e:
            raise RuntimeError("Failed to fetch heightmap") from e
        return np.array(data)

    def get_biomes(self, x, z, width, depth) -> np.ndarray:
        """
        Fetch a 2D array of biome IDs.
        Returns:
            np.ndarray of shape [width, depth], indexed by [x, z].
        """
        data = self.client.get("/biomes", {
            "x": x,
            "z": z,
            "width": width,
            "depth": depth,
        })
        return np.array([list(row) for row in data])

    def get_blocks(self, x, y, z, dx, dy, dz) -> np.ndarray:
        """
        Fetch a 3D array of blocks from the server.
        Returns:
            np.ndarray of shape [dx, dy, dz], indexed by [x, y, z].
        """
        try:
            data = self.client.get("/blocks", {
                "x": x,
                "y": y,
                "z": z,
                "dx": dx,
                "dy": dy,
                "dz": dz
            })
        except Exception as e:
            raise RuntimeError(f"Failed to load blocks at ({x},{y},{z}) size ({dx},{dy},{dz}): {e}")
        return np.array(data)