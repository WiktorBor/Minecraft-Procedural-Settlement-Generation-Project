# world_interface/terrain_loader.py

import numpy as np

class TerrainLoader:

    def __init__(self, client):
        self.client = client

    def get_build_area(self):
        if not self.client.check_build_area():
            print("\n No build area set. Set it in-game first, e.g.:")
            print("   /buildarea set ~ ~ ~ ~199 ~ ~199   (200x200 from your position)")
            print("   Or: /buildarea set x1 y1 z1 x2 y2 z2")
            raise SystemExit(1)
        
        return self.client.get("/buildarea")

    def get_heightmap(self, x, z, width, depth, type):
        data = self.client.get("/heightmap", {
            "x": x,
            "z": z,
            "dx": width,
            "dz": depth,
            "type": type
        })
        return np.array(data)

    def get_biomes(self, x, z, width, depth):
        data = self.client.get("/biomes", {
            "x": x,
            "z": z,
            "width": width,
            "depth": depth,
        })
        return np.array([list(row) for row in data])

    def get_blocks(self, x, y, z, dx, dy, dz):
        return self.client.get("/blocks", {
            "x": x,
            "y": y,
            "z": z,
            "dx": dx,
            "dy": dy,
            "dz": dz
        })