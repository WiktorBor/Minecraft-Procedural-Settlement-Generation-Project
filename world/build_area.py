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
    