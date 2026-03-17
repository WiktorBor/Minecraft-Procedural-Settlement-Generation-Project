from dataclasses import dataclass
from typing import Tuple

@dataclass
class BuildArea:
    x_from: int
    y_from: int
    z_from: int
    x_to: int
    y_to: int
    z_to: int

    @property
    def width(self) -> int:
        return self.x_to - self.x_from + 1

    @property
    def depth(self) -> int:
        return self.z_to - self.z_from + 1

    @property
    def height(self) -> int:
        return self.y_to - self.y_from + 1
    
    def contains(self, x, y, z) -> bool:
        return (
            self.x_from <= x <= self.x_to and
            self.y_from <= y <= self.y_to and
            self.z_from <= z <= self.z_to
        )
    
    def contains_xz(self, x, z) -> bool:
        return (
            self.x_from <= x <= self.x_to and
            self.z_from <= z <= self.z_to
        )
    
    def world_to_index(self, x, z) -> Tuple[int, int]:
        """
        Convert world coordinates to local build area indices.
        """
        
        ix = x - self.x_from
        iz = z - self.z_from
        return ix, iz
    
    def index_to_world(self, i, j) -> Tuple[int, int]:
        """
        Convert local build area indices to world coordinates.
        Raise ValueError if indices are out of bounds.
        """

        if i < 0 or j < 0 or i >= self.width or j >= self.depth:
            raise ValueError(f"{(i,j)} outside build area indices")

        wx = self.x_from + i
        wz = self.z_from + j

        return wx, wz