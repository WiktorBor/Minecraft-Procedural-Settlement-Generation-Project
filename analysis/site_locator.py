"""Finds optimal building sites within terrain."""

import numpy as np
from gdpc import Block


class SiteLocator:
    
    def __init__(self, world_analyser, settlement_area, editor):
        self.world = world_analyser
        self.settlement_area = settlement_area
        self.sites = []
        self.editor = editor
    
    def find_sites(self, max_sites=5, building_size=(7, 7)):
        """
        Find best building sites.
        
        Args:
            building_size: (width, depth) for buildings
            max_sites: Maximum number of sites to return
            
        Returns:
            List of site dictionaries
        """
        print("\n=== SITE LOCATION ===")
        print(f"  Searching for {max_sites} sites ({building_size[0]}x{building_size[1]})...")
        
        width, depth = building_size
        margin = 3

        # Global terrain references
        global_heightmap = self.world.heightmap
        global_slope_map = self.world.slope_map
        global_area = self.world.build_area
        global_water_mask = self.world.water_mask
        global_water_distances = self.world.water_distances

        # Convert settlement area to local indices
        offset_x = self.settlement_area.x_from - global_area.x_from
        offset_z = self.settlement_area.z_from - global_area.z_from

        area_width = self.settlement_area.width
        area_depth = self.settlement_area.depth

        occupied = np.zeros((area_width, area_depth), dtype=bool)
        candidates = []
        
        for i in range(margin, area_width - width - margin):
            for j in range(margin, area_depth - depth - margin):

                if occupied[i-margin:i+width+margin, j-margin:j+depth+margin].any():
                    continue
                
                gx = offset_x + i
                gz = offset_z + j

                if global_water_mask[gx:gx+width, gz:gz+depth].any():
                    continue

                if global_water_distances[gx:gx+width, gz:gz+depth].min() < 4:
                    continue   

                area_heights = global_heightmap[gx:gx+width, gz:gz+depth]
                area_slopes = global_slope_map[gx:gx+width, gz:gz+depth]

                height_range = area_heights.max() - area_heights.min()
                mean_slope = area_slopes.mean()

                if height_range > 2:
                    continue

                flatness_score = max(0, 1 - mean_slope / 2)
                level_score = max(0, 1 -height_range / 3)
                water_proximity = self.world._compute_water_proximity(gx, gz)

                area_score = flatness_score * 0.5 + level_score * 0.3 + water_proximity * 0.2
                
                if area_score > 0.4:
                    candidates.append({
                        'local_x': i,
                        'local_z': j,
                        'score': area_score
                    })
        
        candidates.sort(key=lambda c: c['score'], reverse=True)

        sites = []
        
        for candidate in candidates[:max_sites]:
            if len(sites) >= max_sites:
                break

            i = candidate['local_x']
            j = candidate['local_z']
            
            if occupied[i-margin:i+width+margin,
                        j-margin:j+depth+margin].any():
                continue

            world_x = self.settlement_area.x_from + i
            world_z = self.settlement_area.z_from + j
            
            gx = offset_x + i
            gz = offset_z + j

            base_height = int(global_heightmap[gx, gz])
            
            site = {
                'x': world_x,
                'z': world_z,
                'height': base_height,
                'width': width,
                'depth': depth,
                'score': candidate['score']
            }
            
            sites.append(site)
            
            occupied[
                i-margin:i+width+margin,
                j-margin:j+depth+margin
            ] = True
        
        self.sites = sites
        print(f"  ✓ Found {len(sites)} sites")
        
        for idx, site in enumerate(sites, 1):
            print(f"    Site {idx}: ({site['x']}, {site['z']}) score={site['score']:.2f}")
        
        return sites

    def visualize_sites(self):
        print("\n  Placing site markers...")
        
        for site in self.sites:
            x, z = site['x'], site['z']
            y = site['height']
            
            self.editor.placeBlock((x, y - 1, z), Block('minecraft:gold_block'))
            self.editor.placeBlock((x, y, z), Block('minecraft:beacon'))
        
        self.editor.flushBuffer()
        print(f"  ✓ Placed {len(self.sites)} markers")
