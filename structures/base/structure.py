from __future__ import annotations

from abc import ABC, abstractmethod

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Plot


class Structure(ABC):
    """
    Abstract base class for all placeable structures.

    Subclasses implement `build()` to place blocks in the world for a
    given Plot using the injected editor and analysis data.
    """

    def __init__(self, editor: Editor, analysis: WorldAnalysisResult) -> None:
        self.editor   = editor
        self.analysis = analysis

    @abstractmethod
    def build(self, plot: Plot) -> None:
        """
        Build the structure at the given plot.

        Args:
            plot: A Plot dataclass instance with x, y, z, width, depth, type.
        """