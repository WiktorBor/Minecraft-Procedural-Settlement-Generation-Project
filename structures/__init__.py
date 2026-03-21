"""
Structure generation modules.

Public API
----------
House        – full residential structure (agent + builder composed)
HouseBuilder – low-level block placement for houses (use directly only if
               you need to bypass the agent)
"""

from .house.house import House
from .house.house_grammar import HouseGrammar
from .tower.tower import Tower
from .tower.tower_builder import TowerBuilder
from .fortification.fortification_builder import FortificationBuilder
from .farm.farm import Farm
from .farm.farm_builder import FarmBuilder
from .decoration.decoration import Decoration
from .decoration.decoration_builder import DecorationBuilder

__all__ = [
    "House",
    "HouseGrammar",
    "Tower",
    "TowerBuilder",
    "FortificationBuilder",
    "Farm",
    "FarmBuilder",
    "Decoration",
    "DecorationBuilder",
]