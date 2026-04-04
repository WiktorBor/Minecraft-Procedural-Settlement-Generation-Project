from __future__ import annotations

import logging

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette
from data.settlement_entities import Districts, Plot
from structures.decoration.plot.decoration_builder import DecorationBuilder

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
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette,
    ) -> None:
        self.editor   = editor
        self.analysis = analysis
        self.palette  = palette
        self._builder = DecorationBuilder(editor, palette)

    def build(self, districts: Districts) -> list[tuple[int, int]]:
        """
        Place the appropriate landmark at each district centre.
        Returns all (x, z) cells occupied so they can be added to state.taken.
        """
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
                self._place_dock(cx, cy, cz, area, water, taken)
                logger.info(
                    "Dock placed at fishing district %d centre (%d, %d, %d).",
                    idx, cx, cy, cz,
                )
            else:
                self._builder.build_fountain_at(cx, cy, cz)
                taken.update(
                    (cx - 2 + dx, cz - 2 + dz)
                    for dx in range(5)
                    for dz in range(5)
                )
                logger.info(
                    "Fountain placed at district %d (%s) centre (%d, %d, %d).",
                    idx, dtype, cx, cy, cz,
                )

        return list(taken)

    # ------------------------------------------------------------------

    def _place_dock(self, cx, cy, cz, area, water, taken):
        from structures.misc.dock import Dock, water_facing_rotation

        rotation = water_facing_rotation(cx, cz, area, water)

        wx = cx - _DOCK_W // 2
        wz = cz - _DOCK_D // 2
        wx = max(area.x_from, min(area.x_to - _DOCK_W + 1, wx))
        wz = max(area.z_from, min(area.z_to - _DOCK_D + 1, wz))

        plot = Plot(x=wx, z=wz, y=cy, width=_DOCK_W, depth=_DOCK_D, type="fishing")

        try:
            Dock().build(self.editor, plot, self.palette, rotation=rotation)
        except Exception:
            logger.error(
                "Dock build failed at (%d, %d).", wx, wz, exc_info=True,
            )
            return

        for dx in range(-2, _DOCK_W + 2):
            for dz in range(-2, _DOCK_D + 2):
                taken.add((wx + dx, wz + dz))