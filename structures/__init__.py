"""
Structure generation modules.

Public API
----------
House        – full residential structure (agent + builder composed)
HouseBuilder – low-level block placement for houses (use directly only if
               you need to bypass the agent)
"""

from .house.house import House
from .house.house_builder import HouseBuilder

__all__ = [
    "House",
    "HouseBuilder",
]