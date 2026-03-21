"""
Shape grammar for procedural medieval house generation.

Architecture
------------
Derives from the reference house (small_house.nbt):

    House
      ├── Foundation   cobblestone perimeter + oak_planks floor
      ├── Body         lower storey walls (3 layers), windows, top beam
      ├── Facade       door + front windows on door face
      ├── Ceiling      stripped_spruce_log ring + oak_slab fill + ceiling light
      ├── Roof         tapered dark_oak_stairs upper storey + ridge slab
      ├── Chimney?     cobblestone column + campfire (back corner)
      ├── Interior     bed, crafting table, pot, vines, moss
      └── Details      lantern, porch posts, flowers, potted plant

All four builder classes receive the same Ctx and write blocks directly
via the GDPC editor.

Usage
-----
    grammar = HouseGrammar(editor, palette)
    grammar.build(plot, rotation=0)
"""
from __future__ import annotations

import random
import logging
from pathlib import Path
from typing import Optional

from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from .house_scorer import HouseScorer, HouseParams
from .house_context import Ctx
from .house_body_builder import BodyBuilder
from .house_roof_builder import RoofBuilder
from .house_detail_builder import DetailBuilder

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"
_MAX_RETRIES = 4


class HouseGrammar:
    """
    Procedural medieval house builder using the NBT-derived shape grammar.

    Keeps the same public interface: build(plot, rotation=0).
    """

    def __init__(
        self,
        editor: Editor,
        palette: BiomePalette,
        model_path: Optional[Path] = None,
    ) -> None:
        self.editor  = editor
        self.palette = palette
        self.scorer  = HouseScorer.load(
            model_path if model_path is not None else _DEFAULT_MODEL_PATH
        )
        self.body   = BodyBuilder(editor, palette)
        self.roof   = RoofBuilder(editor, palette)
        self.detail = DetailBuilder(editor, palette)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, plot: Plot, rotation: int = 0) -> None:
        """
        Score up to _MAX_RETRIES parameter sets and build the best one.
        A house is always placed — the highest scorer wins even if it
        doesn't clear the threshold.
        """
        best_ctx:   Optional[Ctx] = None
        best_score: float         = -1.0

        for _ in range(_MAX_RETRIES):
            ctx    = self._make_context(plot, rotation)
            params = self._ctx_to_params(ctx)
            score  = self.scorer.score(params)

            if score > best_score:
                best_score = score
                best_ctx   = ctx

            if self.scorer.passes(params):
                break

        ctx = best_ctx
        logger.debug(
            "HouseGrammar: building %dx%d at (%d,%d,%d) score=%.2f "
            "upper=%s chimney=%s porch=%s",
            ctx.w, ctx.d, ctx.x, ctx.y, ctx.z, best_score,
            ctx.has_upper, ctx.has_chimney, ctx.has_porch,
        )

        self.body.build_foundation(ctx)
        self.body.build_body(ctx)
        self.body.build_facade(ctx)
        self.body.build_ceiling(ctx)
        self.roof.build(ctx)
        if ctx.has_chimney:
            self.detail.build_chimney(ctx)
        self.detail.build_interior(ctx)
        self.detail.build_details(ctx)

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _make_context(self, plot: Plot, rotation: int) -> Ctx:
        w, d = plot.width, plot.depth
        if rotation in (90, 270):
            w, d = d, w

        # Clamp to sizes that produce a well-proportioned reference-style house
        w = max(7, min(w, 11))
        d = max(7, min(d, 11))

        # Snap to odd numbers so mid_x/mid_z land on a whole block
        if w % 2 == 0:
            w -= 1
        if d % 2 == 0:
            d -= 1

        wall_h       = random.choice([3, 3, 4])     # usually 3, occasionally 4
        has_upper    = (w >= 7 and d >= 7 and random.random() < 0.70)
        upper_layers = random.randint(3, 4) if has_upper else 0

        smoke_block = palette_get(self.palette, "smoke", "minecraft:campfire")
        has_chimney = ("campfire" in smoke_block) and (random.random() < 0.80)
        has_porch   = random.random() < 0.45

        door_face = 0 if random.random() < 0.75 else 1

        return Ctx(
            x=plot.x, y=plot.y, z=plot.z,
            w=w, d=d,
            wall_h=wall_h,
            has_upper=has_upper,
            upper_layers=upper_layers,
            has_chimney=has_chimney,
            has_porch=has_porch,
            door_face=door_face,
            palette=self.palette,
        )

    # ------------------------------------------------------------------
    # Ctx → HouseParams for scorer
    # ------------------------------------------------------------------

    def _ctx_to_params(self, ctx: Ctx) -> HouseParams:
        return HouseParams(
            w=ctx.w,
            d=ctx.d,
            wall_h=ctx.wall_h,
            has_upper=ctx.has_upper,
            upper_h=ctx.upper_layers,
            has_chimney=ctx.has_chimney,
            has_porch=ctx.has_porch,
            has_extension=False,
            roof_type="gabled",
            foundation_h=1,
            ext_w=0,
        )