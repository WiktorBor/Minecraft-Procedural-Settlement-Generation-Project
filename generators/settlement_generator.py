"""Main orchestrator for settlement generation."""
from planning.site_locator import SiteLocator
from structures.registry import STRUCTURES
from pathfinding.pathway_builder import build_pathways
from settlement.settlement_planner import SettlementPlanner



class SettlementGenerator:
    
    def __init__(self, editor, analyser, state, config):
        self.editor = editor
        self.analyser = analyser
        self.state = state
        self.config = state
        self.planner = SettlementPlanner(analyser, state, config)
    
    def generate(self, num_buildings=12):
        """
        Generate complete settlement: place structures first, then pathways.

        Args:
            num_buildings: Number of buildings to generate (e.g. 12-15 for village).
        """
        print("\n" + "="*50)
        print("SETTLEMENT GENERATOR")
        print("="*50)
        
        # Phase 1: Locate building sites
        self.planner.plan()
        sites = self._locate_sites(self.analyser, num_buildings)
        
        # Phase 2: Generate buildings
        self._generate_buildings(self.analyser, sites)
        
        # Phase 3: Generate pathways between building fronts
        self._generate_pathways(self.analyser)
        
        # Phase 4: Finalize
        self._finalize()
        
        print("\n" + "="*50)
        print("✓ SETTLEMENT GENERATION COMPLETE")
        print("="*50)
        print(f"\nGenerated {len(self.state.buildings)} buildings")
        print("\nCheck Minecraft to see your settlement!")
    
    # Private methods for each phase
    
    def _locate_sites(self,analysis, num_buildings):
        print("\n[Phase 2] Locating building sites")

        site_locator = SiteLocator(analysis, self.editor, plots=self.state.plots)
        sites = site_locator.find_sites(max_sites=num_buildings)
        print(f" {len(sites)} building sites determined.")
        return sites

    def _generate_buildings(self, analysis, sites):
        print("\n[Phase 3] Building Generation")
        
        for idx, site in enumerate(sites, 1):
            structure_type = "house"
            structure_class = STRUCTURES[structure_type]

            structure = structure_class(self.editor, analysis)
            print(f"  Building {idx}/{len(sites)} at {site} ({structure_type})")

            area = site["area"]
            structure.build(area)

            # Store data in a shape that the pathfinding code expects.
            building_data = {
                "type": structure_type,
                "position": (area.x_from, area.y_from, area.z_from),
                "size": (area.width, area.height, area.depth),
                "area": area,
                "score": site["score"],
            }
            self.state.buildings.append(building_data)
        
        print(f"  ✓ Generated {len(self.state.buildings)} buildings")
    
    def _generate_pathways(self, analysis):
        print("\n[Phase 3b] Pathway Generation")
        if not self.state.buildings:
            print("  No buildings to connect.")
            return
        build_pathways(analysis, self.state.buildings, self.editor)
        print("  ✓ Pathways placed between building fronts")
    
    def _finalize(self):
        print("\n[Phase 4] Finalizing...")
        print("  Flushing blocks to Minecraft...")
        
        self.editor.flushBuffer()
        
        print("  ✓ All blocks placed!")
