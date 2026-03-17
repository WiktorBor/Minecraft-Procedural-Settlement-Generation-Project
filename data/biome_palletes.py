from typing import Dict

# Biome material palettes (constant)
BIOME_PALETTES: Dict[str, Dict[str, str]] = {
    'plains': {
        'wall': 'minecraft:oak_planks',
        'roof': 'minecraft:dark_oak_stairs',
        'floor': 'minecraft:oak_planks',
        'foundation': 'minecraft:cobblestone',
        'path': 'minecraft:dirt_path',
        'accent': 'minecraft:oak_log'
    },
    'desert': {
        'wall': 'minecraft:sandstone',
        'roof': 'minecraft:smooth_sandstone_stairs',
        'floor': 'minecraft:sandstone',
        'foundation': 'minecraft:sandstone',
        'path': 'minecraft:sand',
        'accent': 'minecraft:cut_sandstone'
    },
    'taiga': {
        'wall': 'minecraft:spruce_planks',
        'roof': 'minecraft:spruce_stairs',
        'floor': 'minecraft:spruce_planks',
        'foundation': 'minecraft:stone',
        'path': 'minecraft:gravel',
        'accent': 'minecraft:spruce_log'
    },
    'mountain': {
        'wall': 'minecraft:stone_bricks',
        'roof': 'minecraft:stone_brick_stairs',
        'floor': 'minecraft:stone_bricks',
        'foundation': 'minecraft:cobblestone',
        'path': 'minecraft:cobblestone',
        'accent': 'minecraft:stone'
    }
}


def get_biome_palette(biome_type: str = 'plains') -> Dict[str, str]:
    """
    Get the block palette for a given biome type.

    Parameters
    ----------
    biome_type : str
        One of 'plains', 'desert', 'taiga', 'mountain'.

    Returns
    -------
    Dict[str, str]
        Mapping of material roles to Minecraft block IDs:
        'wall', 'roof', 'floor', 'foundation', 'path', 'accent'.
    """
    return BIOME_PALETTES.get(biome_type, BIOME_PALETTES['plains'])