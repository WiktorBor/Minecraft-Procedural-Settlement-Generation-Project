from structures.base.structure_agent import StructureAgent
from data.settlement_entities import Plot

class HouseAgent(StructureAgent):
    """
    Agent responsible for deciding where and how to build houses.
    Analyzes terrain and returns building parameters.
    """

    def decide(self, plot: Plot) -> dict:
        """
        Analyze the site and return building decisions.
        
        Args:
            site: Dictionary with x, z, width, depth
            
        Returns:
            Dictionary with building parameters
        """
        patch = self.extract_patch(plot)
        if not self.is_flat(patch, tolerance=1):
            # If terrain is too uneven, we might choose not to build
            return {
                "build": False
            }
        
        import random
        rotation = random.choice([0, 90, 180, 270])
        return {
            "build": True,
            "rotation": rotation
        }

        # # Simple decision logic based on terrain features
        # slope = self.compute_slope(patch)

        # roof_type = "gabled"
        # floors = 1
        
        # if slope > 2:
        #     roof_type = "steep"
        
        # if plot.width > 10:
        #     floors = 2

        # return {
        #     "roof_type": roof_type,
        #     "floors": floors,
        #     "chimney": True
        # }