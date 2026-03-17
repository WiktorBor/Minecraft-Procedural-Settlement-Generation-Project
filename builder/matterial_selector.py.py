from data.biome_palettes import get_biome_palette

def _path_blocks_from_biome(world) -> str:
    """Sample biome at center of best_area and return path block id."""
    best_area = world.best_area
    cx = best_area.x_from + best_area.width // 2
    cz = best_area.z_from + best_area.depth // 2
    build_area = world.build_area
    bi, bj = build_area.world_to_index(cx, cz)

    if 0 <= bi < world.biomes.shape[0] and 0 <= bj < world.biomes.shape[1]:
        biome_id = str(world.biomes[bi, bj])
        if "desert" in biome_id:
            return get_biome_palette("desert")["path"]
        if "taiga" in biome_id or "snow" in biome_id:
            return get_biome_palette("taiga")["path"]
        if "savanna" in biome_id or "badlands" in biome_id:
            return get_biome_palette("mountain")["path"]
    return get_biome_palette("plains")["path"]
