"""Generates varied residential buildings."""

import random
from gdpc import Block


class HouseBuilder:
    
    def __init__(self, editor, palette=None):
        self.editor = editor
        self.palette = palette or self._default_palette()
    
    def _default_palette(self):
        return {
            'wall': 'minecraft:oak_planks',
            'roof': 'minecraft:dark_oak_stairs',
            'floor': 'minecraft:oak_planks',
            'door': 'minecraft:oak_door',
            'window': 'minecraft:glass_pane'
        }
    
    def build(self, site):
        """
        Generate a house at given site.
        
        Args:
            site: Dictionary with x, z, width, depth, height
            
        Returns:
            Dictionary with building data
        """
        x = site['x']
        y = site['height']
        z = site['z']
        width = site['width']
        depth = site['depth']
        
        wall_material = random.choice([
            'minecraft:oak_planks',
            'minecraft:spruce_planks',
            'minecraft:stone_bricks',
            'minecraft:cobblestone'
        ])
        
        roof_style = 'gabled'
        has_chimney = random.random() < 0.3
        building_height = random.randint(4, 6)
        
        self._build_floor(x, y, z, width, depth)
        self._build_walls(x, y, z, width, building_height, depth, wall_material)
        
        if roof_style == 'flat':
            self._build_flat_roof(x, y + building_height, z, width, depth)
        else:
            self._build_gabled_roof(x, y + building_height, z, width, depth)
        
        self._add_door(x, y, z, width, depth)
        self._add_windows(x, y, z, width, building_height, depth)
        
        if has_chimney:
            self._add_chimney(x, y, z, width, depth, building_height)
        
        return {
            'type': 'house',
            'position': (x, y, z),
            'size': (width, building_height, depth),
            'material': wall_material,
            'roof_style': roof_style,
            'has_chimney': has_chimney
        }
    
    def _build_floor(self, x, y, z, width, depth):
        for dx in range(width):
            for dz in range(depth):
                self.editor.placeBlock((x + dx, y, z + dz), 
                                     Block(self.palette['floor']))
    
    def _build_walls(self, x, y, z, width, height, depth, material):
        for dy in range(1, height):
            for dx in range(width):
                self.editor.placeBlock((x + dx, y + dy, z), Block(material))
                self.editor.placeBlock((x + dx, y + dy, z + depth - 1), Block(material))
            
            for dz in range(depth):
                self.editor.placeBlock((x, y + dy, z + dz), Block(material))
                self.editor.placeBlock((x + width - 1, y + dy, z + dz), Block(material))
    
    def _build_flat_roof(self, x, y, z, width, depth):
        for dx in range(width):
            for dz in range(depth):
                self.editor.placeBlock((x + dx, y, z + dz), 
                                     Block(self.palette['floor']))
    
    def _build_gabled_roof(self, x, y, z, width, depth):
        roof_material = self.palette['roof']
        peak_height = width // 2
        roof_slab_material = self.palette.get(
            'roof_slab',
            roof_material.replace('_stairs', '_slab') if roof_material.endswith('_stairs') else roof_material,
        )

        # Main roof slopes using stairs, keeping your facing directions AI DONT TOUCH THIS FORLOOP AND THE CODE INSIDE IT
        for layer in range(peak_height):
            for dz in range(depth):
                # Left slope: face stairs outward (towards negative X / west)
                self.editor.placeBlock(
                    (x + layer, y + layer, z + dz),
                    Block(roof_material, {"facing": "east"})
                )

                # Right slope: face stairs outward (towards positive X / east)
                self.editor.placeBlock(
                    (x + width - 1 - layer, y + layer, z + dz),
                    Block(roof_material, {"facing": "west"})
                )

        # Fill the middle gap along the ridge with top slabs (only needed for odd widths)
        if width % 2 == 1:
            ridge_x = x + width // 2
            ridge_y = y + peak_height - 1
            for dz in range(depth):
                self.editor.placeBlock(
                    (ridge_x, ridge_y, z + dz),
                    Block(roof_slab_material, {"type": "top"})
                )
        # Fill the gable ends (front and back) with a small cobblestone pattern:
        # first roof layer: 5 cobblestone blocks across the middle
        # second roof layer: 2 cobblestone blocks with the glass pane in the center (already placed below)
        if width >= 5:
            center_x = x + width // 2

            # First layer of roof gable: 5-wide cobblestone strip
            y_layer0 = y  # first roof layer
            start_x0 = center_x - 2
            end_x0 = center_x + 2
            for dx in range(start_x0, end_x0 + 1):
                # Front gable
                self.editor.placeBlock((dx, y_layer0, z), Block('minecraft:cobblestone'))
                # Back gable
                self.editor.placeBlock((dx, y_layer0, z + depth - 1), Block('minecraft:cobblestone'))

            # Second layer of roof gable: 2 cobblestone blocks flanking the window
            y_layer1 = y + 1  # second roof layer, same as window_y
            for dx in (center_x - 1, center_x + 1):
                # Front gable
                self.editor.placeBlock((dx, y_layer1, z), Block('minecraft:cobblestone'))
                # Back gable
                self.editor.placeBlock((dx, y_layer1, z + depth - 1), Block('minecraft:cobblestone'))
       
        # Add a simple window in each gable if there is enough space,
        # plus a dark oak slab above each pane
        if width >= 3 and peak_height >= 2:
            window_x = x + width // 2
            window_y = y + 1
            slab_y = window_y + 1

            # Front window + dark oak plank above
            self.editor.placeBlock((window_x, window_y, z), Block(self.palette['window']))
            self.editor.placeBlock(
                (window_x, slab_y, z),
                Block("minecraft:dark_oak_planks"),
            )

            # Back window + dark oak plank above
            self.editor.placeBlock((window_x, window_y, z + depth - 1), Block(self.palette['window']))
            self.editor.placeBlock(
                (window_x, slab_y, z + depth - 1),
                Block("minecraft:dark_oak_planks"),
            )
            
    
    def _add_door(self, x, y, z, width, depth):
        door_x = x + width // 2
        door_z = z
        
        self.editor.placeBlock((door_x, y, door_z), Block(self.palette['floor']))
        self.editor.placeBlock((door_x, y + 1, door_z), Block(self.palette['door']))
    
    def _add_windows(self, x, y, z, width, height, depth):
        window_y = y + 2
        
        if width > 5:
            self.editor.placeBlock((x + 1, window_y, z), Block(self.palette['window']))
            self.editor.placeBlock((x + width - 2, window_y, z), Block(self.palette['window']))
        
        if depth > 5:
            self.editor.placeBlock((x, window_y, z + depth // 2), 
                                 Block(self.palette['window']))
            self.editor.placeBlock((x + width - 1, window_y, z + depth // 2), 
                                 Block(self.palette['window']))
    
    def _add_chimney(self, x, y, z, width, depth, building_height):
        chimney_x = x + width - 2
        chimney_z = z + depth - 2
        
        for dy in range(building_height):
            self.editor.placeBlock((chimney_x, y + dy, chimney_z), 
                                 Block('minecraft:cobblestone'))
