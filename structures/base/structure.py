from abc import ABC, abstractmethod

class Structure(ABC):
    """
    Abstract base class for structures.
    """

    def __init__(self, editor, world):
        self.editor = editor
        self.world = world

    @abstractmethod
    def build(self, plot):
        """
        Build the structure at the given plot.
        
        Args:
            plot:
                {
                    'x': int,
                    'y': int,
                    'z': int,
                    'width': int,
                    'depth': int,
                    'type': str
                }
        """
        pass