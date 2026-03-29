from __future__ import annotations

import logging

from gdpc.editor import Editor

from data.analysis_results import WorldAnalysisResult
from data.biome_palettes import BiomePalette
from data.settlement_entities import Districts
from structures.decoration.decoration_builder import DecorationBuilder

logger = logging.getLogger(__name__)


class DistrictMarker:
    """
    Places a fountain at the centre of every district using DecorationBuilder.
    """

    def __init__(
        self,
        editor: Editor,
        analysis: WorldAnalysisResult,
        palette: BiomePalette,
    ) -> None:
        self.analysis = analysis
        self._builder = DecorationBuilder(editor, palette)

    def build(self, districts: Districts) -> list[tuple[int, int]]:
        """
        Place a fountain at each district centre.
        Returns all (x, z) cells occupied so they can be added to state.taken.
        """
        taken: set[tuple[int, int]] = set()
        area = self.analysis.best_area

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

            self._builder.build_fountain_at(cx, cy, cz)

            taken.update(
                (cx - 2 + dx, cz - 2 + dz)
                for dx in range(5)
                for dz in range(5)
            )
            
            logger.info(
                "Fountain placed at district %d (%s) centre (%d, %d, %d).",
                idx, district.type, cx, cy, cz,
            )

        return list(taken)