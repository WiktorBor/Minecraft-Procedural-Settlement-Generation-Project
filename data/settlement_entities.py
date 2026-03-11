from dataclasses import dataclass

@dataclass
class Plot:
    x: int
    z: int
    width: int
    depth: int

@dataclass (frozen=True)
class RoadCell:
    x: int
    z: int

@dataclass
class District:
    x: int
    z: int
    width: int
    depth: int
    type: str

@dataclass
class Building:
    x: int
    z: int
    width: int
    depth: int
    type: str