"""
builder/material_selector.py
-----------------------------
Utility helpers for selecting material block IDs from world state.
"""
from __future__ import annotations

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import get_biome_palette


def path_block_from_biome(world: WorldAnalysisResult) -> str:
    """
    Sample the biome at the centre of best_area and return the appropriate
    path block ID.

    Parameters
    ----------
    world : WorldAnalysisResult
        Must have biomes populated (shape matches best_area).

    Returns
    -------
    str
        A Minecraft block ID suitable for path placement.
    """
    best_area = world.best_area

    # Centre in local index space — biomes is already sliced to best_area.
    bi = best_area.width  // 2
    bj = best_area.depth  // 2

    if 0 <= bi < world.biomes.shape[0] and 0 <= bj < world.biomes.shape[1]:
        biome_id = str(world.biomes[bi, bj])
        if "desert" in biome_id:
            return get_biome_palette("desert")["path"]
        if "taiga" in biome_id or "snow" in biome_id:
            return get_biome_palette("taiga")["path"]
        if "savanna" in biome_id or "badlands" in biome_id:
            return get_biome_palette("mountain")["path"]

    return get_biome_palette("plains")["path"]