from __future__ import annotations

import logging

from data.analysis_results import WorldAnalysisResult
from palette.palette_system import PaletteSystem
from data.settlement_entities import Districts, Plot
from structures.decoration.plot.decoration_builder import DecorationBuilder
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)

_DOCK_W = 14
_DOCK_D = 10


class DistrictMarker:
    """
    Places a landmark at the centre of every district:
      • fishing districts → Dock (oriented toward nearest water)
      • all other districts → fountain
    """

    def __init__(
        self,
        analysis: WorldAnalysisResult,
        palette: PaletteSystem,
    ) -> None:
        self.analysis = analysis
        self.palette  = palette
        self._builder = DecorationBuilder(palette)

    def build(self, districts: Districts) -> tuple[BlockBuffer, list[tuple[int, int]]]:
        """
        Build landmark buffers for every district centre.
        Returns (merged_buffer, taken_cells).
        """
        master  = BlockBuffer()
        taken: set[tuple[int, int]] = set()
        area  = self.analysis.best_area
        water = self.analysis.water_mask.astype(bool)

        for idx, district in enumerate(districts.district_list):
            cx = int(district.center_x)
            cz = int(district.center_z)

            if not area.contains_xz(cx, cz):
                logger.warning(
                    "District %d centre (%d, %d) outside build area — skipping.",
                    idx, cx, cz,
                )
                continue

            li, lj = area.world_to_index(cx, cz)
            cy = int(self.analysis.heightmap_ground[li, lj])

            dtype = districts.types.get(idx, "")

            if dtype == "fishing":
                buf = self._place_dock(cx, cy, cz, area, water, taken)
                logger.info(
                    "Dock placed at fishing district %d centre (%d, %d, %d).",
                    idx, cx, cy, cz,
                )
            else:
                buf = self._builder.build_fountain_at(cx, cy, cz)
                taken.update(
                    (cx - 2 + dx, cz - 2 + dz)
                    for dx in range(5)
                    for dz in range(5)
                )
                logger.info(
                    "Fountain placed at district %d (%s) centre (%d, %d, %d).",
                    idx, dtype, cx, cy, cz,
                )

            if buf:
                master.merge(buf)

        return master, list(taken)

    # ------------------------------------------------------------------

    def _place_dock(self, cx, cy, cz, area, water, taken) -> BlockBuffer | None:
        from structures.misc.dock import Dock, water_facing_rotation

        rotation = water_facing_rotation(cx, cz, area, water)

        wx = cx - _DOCK_W // 2
        wz = cz - _DOCK_D // 2
        wx = max(area.x_from, min(area.x_to - _DOCK_W + 1, wx))
        wz = max(area.z_from, min(area.z_to - _DOCK_D + 1, wz))

        plot = Plot(x=wx, z=wz, y=cy, width=_DOCK_W, depth=_DOCK_D, type="fishing")

        try:
            buf = Dock().build(None, plot, self.palette, rotation=rotation)
        except Exception:
            logger.error("Dock build failed at (%d, %d).", wx, wz, exc_info=True)
            return None

        for dx in range(-2, _DOCK_W + 2):
            for dz in range(-2, _DOCK_D + 2):
                taken.add((wx + dx, wz + dz))

        return buf
