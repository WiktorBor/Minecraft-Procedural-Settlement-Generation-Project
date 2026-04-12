from __future__ import annotations
import logging
import random

from data.analysis_results import WorldAnalysisResult
from data.settlement_entities import Districts, Plot
from structures.base.build_context import BuildContext
from structures.grammar.decoration_grammar import rule_fountain, rule_well

logger = logging.getLogger(__name__)

class DistrictMarker:
    """
    Places landmarks at district centers directly into the context buffer.
    """
    def __init__(self, analysis: WorldAnalysisResult, ctx: BuildContext) -> None:
        self.analysis = analysis
        self.ctx = ctx # Context holds both the buffer and the palette

    def build(self, districts: Districts) -> list[tuple[int, int]]:
        """
        Builds landmarks and returns 'taken' cells for avoidance.
        """
        taken: set[tuple[int, int]] = set()
        area = self.analysis.best_area
        water = self.analysis.water_mask.astype(bool)

        for idx, district in enumerate(districts.district_list):
            cx, cz = int(district.center_x), int(district.center_z)

            if not area.contains_xz(cx, cz):
                continue

            li, lj = area.world_to_index(cx, cz)
            cy = int(self.analysis.heightmap_ground[li, lj])
            dtype = districts.types.get(idx, "")

            if dtype == "fishing":
                # For now, just a fountain until Dock orchestrator is verified
                rule_fountain(self.ctx, cx, cy, cz)
                self._mark_taken(cx, cz, 5, taken)
            else:
                # Random choice between Fountain and Well
                choice = random.choice(["fountain", "well"])
                if choice == "well":
                    rule_well(self.ctx, cx - 1, cy, cz - 1)
                    self._mark_taken(cx, cz, 3, taken)
                else:
                    rule_fountain(self.ctx, cx, cy, cz)
                    self._mark_taken(cx, cz, 5, taken)
                
                logger.info(f"Marker '{choice}' placed at district {idx}.")

        return list(taken)

    def _mark_taken(self, cx: int, cz: int, size: int, taken_set: set):
        offset = size // 2
        for dx in range(-offset, offset + 1):
            for dz in range(-offset, offset + 1):
                taken_set.add((cx + dx, cz + dz))