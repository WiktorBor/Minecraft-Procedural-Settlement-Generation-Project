"""Main orchestrator for settlement generation."""
from analysis.site_locator import SiteLocator
from world_analysis import WorldAnalyser
from world.build_area import BuildArea


class SettlementGenerator:
    
    def __init__(self, editor, client):
        self.editor = editor
        self.client = client

        self.world_analyser: WorldAnalyser | None = None
        self.best_area: BuildArea | None = None
        self.house_builder = None
        self.buildings = []
        self.site_locator: SiteLocator | None = None
        self.sites = []
    
    def generate(self, num_buildings=3):
        """
        Generate complete settlement.
        
        Args:
            num_buildings: Number of buildings to generate
            visualize: Show debug visualizations in Minecraft
        """
        print("\n" + "="*50)
        print("SETTLEMENT GENERATOR")
        print("="*50)
        
        # Phase 1: Analyse world and find best building area
        self._setup_world_analysis()
        
        # Phase 2: Locate building sites
        self._locate_sites(num_buildings)
        
        # Phase 3: Generate buildings
        self._generate_buildings()
        
        # Phase 4: Finalize
        self._finalize()
        
        print("\n" + "="*50)
        print("✓ SETTLEMENT GENERATION COMPLETE")
        print("="*50)
        print(f"\nGenerated {len(self.buildings)} buildings")
        print("\nCheck Minecraft to see your settlement!")
    
    # Private methods for each phase
    def _setup_world_analysis(self):
        print("\n[Phase 1] Setup")

        # Initialise WorldAnaliser
        self.world_analyser = WorldAnalyser(self.client)
        self.world_analyser.prepare()

        self.best_area = self.world_analyser.best_area

        self.site_locator = SiteLocator(self.world_analyser, self.best_area, self.editor)
    
    def _locate_sites(self, num_buildings):
        print("\n[Phase 2] Locating building sites")

        self.sites = self.site_locator.find_sites(num_buildings)
        print(f" {len(self.sites)} building sites determined.")

    def _generate_buildings(self):
        print("\n[Phase 3] Building Generation")
        from structures.house_builder import HouseBuilder
        self.house_builder = HouseBuilder(self.editor)
        
        for idx, site in enumerate(self.sites, 1):
            print(f"  Building {idx}/{len(self.sites)} at {site}")
            building_data = self.house_builder.build(site)
            self.buildings.append(building_data)
        
        print(f"  ✓ Generated {len(self.buildings)} buildings")
    
    def _finalize(self):
        print("\n[Phase 4] Finalizing...")
        print("  Flushing blocks to Minecraft...")
        
        self.editor.flushBuffer()
        
        print("  ✓ All blocks placed!")
