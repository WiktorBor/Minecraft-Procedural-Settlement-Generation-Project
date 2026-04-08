"""
structures/misc/cottage.py
---------------------------
Half-timbered medieval cottage built via HouseGrammar.

Uses the same grammar + scorer pipeline as the standard house, with two forced
parameters:
  - roof_type = "cross"
  - cross_side = connection_side  (arm faces the side that connects to a bridge
                                   or road, e.g. "west" for the tavern bridge)

Can be used standalone (CottageBuilder.build / build_at) or embedded inside a
larger structure (e.g. Tavern) via CottageBuilder().build_at(..., wall_h=...).
"""
from __future__ import annotations

from palette.palette_system import PaletteSystem
from data.settlement_entities import Plot
from structures.house.house_grammar import HouseGrammar
from structures.house.house_ngram_scorer import HouseNgramScorer
from structures.house.house_scorer import HouseScorer
from world_interface.block_buffer import BlockBuffer


class CottageBuilder:
    """
    Half-timbered medieval cottage built via HouseGrammar.

    Recommended plot: width >= 7, depth >= 7.

    connection_side — which face connects to an adjacent structure or road
    ("north"|"south"|"east"|"west").  The cross-gabled roof arm extends
    toward that side.  Defaults to "west".

    wall_h — when given, overrides the grammar's sampled wall height so the
    caller can align surrounding structures (e.g. a bridge) to the roof line.

    scorer / ngram_scorer — pre-loaded model instances.  Pass these from the
    StructureSelector singletons to avoid repeated disk reads.
    """

    def build(
        self,
        plot: Plot,
        palette: PaletteSystem,
        rotation: int = 0,
        connection_side: str = "west",
        wall_h: int | None = None,
        scorer: HouseScorer | None = None,
        ngram_scorer: HouseNgramScorer | None = None,
    ) -> BlockBuffer:
        """Build on a Plot. Returns a BlockBuffer."""
        overrides: dict = {"roof_type": "cross", "cross_side": connection_side}
        if wall_h is not None:
            overrides["wall_h"] = wall_h
        grammar = HouseGrammar(
            palette,
            scorer=scorer,
            ngram_scorer=ngram_scorer,
            forced_ctx_overrides=overrides,
        )
        return grammar.build(plot, rotation=rotation)

    def build_at(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        palette: PaletteSystem,
        rotation: int = 0,
        connection_side: str = "west",
        wall_h: int | None = None,
        scorer: HouseScorer | None = None,
        ngram_scorer: HouseNgramScorer | None = None,
    ) -> BlockBuffer:
        """Build at explicit coordinates. Returns a BlockBuffer."""
        plot = Plot(x=x, y=y, z=z, width=w, depth=d, type="residential")
        return self.build(
            plot, palette,
            rotation=rotation,
            connection_side=connection_side,
            wall_h=wall_h,
            scorer=scorer,
            ngram_scorer=ngram_scorer,
        )
