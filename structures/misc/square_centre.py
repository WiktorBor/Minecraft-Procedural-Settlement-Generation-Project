"""Circular stone plaza with a centrepiece fountain scaled to the plot."""
from __future__ import annotations

import math

from gdpc import Block

from data.biome_palettes import BiomePalette
from data.settlement_entities import Plot
from world_interface.block_buffer import BlockBuffer


class SquareCentre:
    """
    Circular stone plaza with a centrepiece fountain.

    Radius scales with the smaller of (width, depth).
    Falls back to simple rectangular paving for very small plots (radius < 3).
    """

    _STONE_MIX = [
        "minecraft:stone_bricks",
        "minecraft:cobblestone",
        "minecraft:andesite",
    ]

    def build(
        self,
        _editor,
        plot: Plot,
        palette: BiomePalette | None = None,
        rotation: int = 0,
    ) -> BlockBuffer:
        buffer = BlockBuffer()

        # All geometry is centred — compute plaza centre, not corner
        cx = plot.x + plot.width  // 2
        cy = plot.y
        cz = plot.z + plot.depth // 2

        radius = min(plot.width, plot.depth) // 2

        if radius < 3:
            self._build_simple_paving(buffer, cx, cy, cz, plot.width, plot.depth)
            return buffer

        if radius >= 8:
            fountain_style   = "grand_spire"
            effective_radius = min(radius, 25)
            clear_height     = 35
        else:
            fountain_style   = "small_fountain"
            effective_radius = radius
            clear_height     = 15

        # Fill ground beneath fountain to prevent water leaks
        self._fill_foundation(buffer, cx, cz, effective_radius + 2, cy)

        # Circular plaza floor + air clearing
        for ix in range(cx - effective_radius, cx + effective_radius + 1):
            for iz in range(cz - effective_radius, cz + effective_radius + 1):
                if math.sqrt((ix - cx) ** 2 + (iz - cz) ** 2) <= effective_radius:
                    b_type = self._STONE_MIX[(ix ^ iz) % len(self._STONE_MIX)]
                    buffer.place(ix, cy, iz, Block(b_type))
                    for iy in range(cy + 1, cy + clear_height):
                        buffer.place(ix, iy, iz, Block("minecraft:air"))

        # Fountain centrepiece
        if fountain_style == "grand_spire":
            self._build_grand_spire(buffer, cx, cy, cz, effective_radius)
        else:
            self._build_small_fountain(buffer, cx, cy, cz, effective_radius)

        return buffer

    def _build_grand_spire(
        self, buffer: BlockBuffer,
        cx: int, cy: int, cz: int,
        radius: int,
    ) -> None:
        # --- Outer water basin ring ---
        r_outer_sq = radius * radius
        r_slab_sq  = (radius - 1) * (radius - 1)
        r_inner_sq = (radius - 2) * (radius - 2)

        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                dist_sq = dx ** 2 + dz ** 2
                if r_inner_sq < dist_sq <= r_outer_sq:
                    buffer.place(cx + dx, cy + 1, cz + dz, Block("minecraft:stone_bricks"))
                    if dist_sq <= r_slab_sq:
                        buffer.place(cx + dx, cy + 2, cz + dz, Block("minecraft:stone_brick_slab"))
                elif dist_sq <= r_inner_sq:
                    buffer.place(cx + dx, cy + 1, cz + dz, Block("minecraft:water"))

        # --- Central mossy stone-brick column with tapering slab ledges ---
        tier_y_to_radius = {cy + 6: 4, cy + 12: 3, cy + 18: 2}

        for iy in range(cy + 1, cy + 22):
            for dx in range(-1, 2):
                for dz in range(-1, 2):
                    # Top layer is a plus shape — skip corners
                    if iy == cy + 21 and abs(dx) == 1 and abs(dz) == 1:
                        continue
                    buffer.place(cx + dx, iy, cz + dz, Block("minecraft:mossy_stone_bricks"))

            # Slab ledge at this tier Y
            if iy in tier_y_to_radius:
                pr    = tier_y_to_radius[iy]
                pr_sq = pr * pr
                for dx in range(-pr, pr + 1):
                    for dz in range(-pr, pr + 1):
                        dist_sq   = dx ** 2 + dz ** 2
                        in_pillar = abs(dx) <= 1 and abs(dz) <= 1
                        if dist_sq <= pr_sq and not in_pillar:
                            buffer.place(cx + dx, iy, cz + dz,
                                         Block("minecraft:stone_brick_slab", {"type": "top"}))

        # --- Cap ---
        buffer.place(cx, cy + 22, cz, Block("minecraft:water"))
        buffer.place(cx, cy + 23, cz, Block("minecraft:oak_trapdoor", {"open": "false"}))
        buffer.place(cx, cy + 24, cz, Block("minecraft:glowstone"))

    def _build_small_fountain(
        self, buffer: BlockBuffer,
        cx: int, cy: int, cz: int,
        radius: int,
    ) -> None:
        tiers = [
            (radius - 1,               1, "minecraft:smooth_stone"),
            (max(1, int((radius - 1) * 0.7)), 2, "minecraft:smooth_stone"),
            (max(1, int((radius - 1) * 0.4)), 3, "minecraft:smooth_stone"),
        ]
        for r, h, block in tiers:
            if r < 1:
                continue
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if dx ** 2 + dz ** 2 <= r * r:
                        buffer.place(cx + dx, cy + h, cz + dz, Block(block))

        basin_r = max(1, int(tiers[-1][0] * 0.8))
        for dx in range(-basin_r, basin_r + 1):
            for dz in range(-basin_r, basin_r + 1):
                if dx ** 2 + dz ** 2 <= basin_r ** 2:
                    buffer.place(cx + dx, cy + 3, cz + dz, Block("minecraft:water"))
                    buffer.place(cx + dx, cy + 2, cz + dz, Block("minecraft:sea_lantern"))

    def _fill_foundation(
        self, buffer: BlockBuffer,
        cx: int, cz: int,
        radius: int, y_top: int,
        depth: int = 20,
    ) -> None:
        """Fill a solid stone column downward so the plaza never floats over voids."""
        stone = Block("minecraft:stone")
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if dx ** 2 + dz ** 2 <= radius ** 2:
                    for dy in range(1, depth + 1):
                        buffer.place(cx + dx, y_top - dy, cz + dz, stone)

    def _build_simple_paving(
        self, buffer: BlockBuffer,
        cx: int, cy: int, cz: int,
        w: int, d: int,
    ) -> None:
        """Rectangular stone-brick paving for very small plots."""
        for ix in range(cx - w // 2, cx + w // 2):
            for iz in range(cz - d // 2, cz + d // 2):
                buffer.place(ix, cy, iz, Block("minecraft:stone_bricks"))