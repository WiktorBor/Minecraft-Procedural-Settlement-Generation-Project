from dataclasses import dataclass

@dataclass
class BuildArea:
    x_from: int
    y_from: int
    z_from: int
    x_to: int
    y_to: int
    z_to: int

    @property
    def width(self):
        return self.x_to - self.x_from + 1

    @property
    def depth(self):
        return self.z_to - self.z_from + 1

    @property
    def height(self):
        return self.y_to - self.y_from + 1
    
    def contains(self, x, y, z):
        return (
            self.x_from <= x <= self.x_to and
            self.y_from <= y <= self.y_to and
            self.z_from <= z <= self.z_to
        )
    
    def contains_xz(self, x, z):
        return (
            self.x_from <= x <= self.x_to and
            self.z_from <= z <= self.z_to
        )
    
    def world_to_index(self, x, z):
        if not self.build_area.contains_xz(x, z):
            raise ValueError("Coordinates out of build area bounds")
        
        i = x - self.build_area.x_from
        j = z - self.build_area.z_from
        return i, j
    
    def index_to_world(self, i, j):

        if i < 0 or j < 0 or i >= self.width or j >= self.depth:
            raise ValueError(f"{(i,j)} outside build area indices")

        x = self.x_from + i
        z = self.z_from + j

        return x, z