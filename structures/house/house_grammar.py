"""
Shape grammar for procedural medieval house generation.

    House
      ├── Foundation   cobblestone perimeter + floor
      ├── Body         lower storey walls + windows + top beam
      ├── Facade       door face
      ├── Ceiling      beam ring + slab fill + interior light
      ├── Upper?       half-timbered upper storey walls  (BodyBuilder)
      ├── Roof         pyramid | gabled | cross          (RoofBuilder)
      ├── Chimney?     cobblestone column + campfire
      ├── Interior     bed, crafting table, pot, vines
      └── Details      lantern, porch, flowers

Usage
-----
    grammar = HouseGrammar(editor, palette)
    grammar.build(plot, rotation=0)
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from structures.house.house_body_builder import BodyBuilder
from structures.house.house_context import Ctx
from structures.house.house_detail_builder import DetailBuilder
from structures.house.house_ngram_scorer import BlockSequenceRecorder, HouseNgramScorer
from structures.house.house_roof_builder import RoofBuilder
from structures.house.house_scorer import HouseParams, HouseScorer

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"
_MAX_RETRIES = 4


class HouseGrammar:

    def __init__(
        self,
        editor: Editor,
        palette: BiomePalette,
        model_path: Path | None = None,
        scorer: HouseScorer | None = None,
        ngram_scorer: HouseNgramScorer | None = None,
    ) -> None:
        self.editor  = editor
        self.palette = palette
        self.scorer  = scorer if scorer is not None else HouseScorer.load(
            model_path if model_path is not None else _DEFAULT_MODEL_PATH
        )
        if ngram_scorer is not None:
            self.ngram_scorer = ngram_scorer
        else:
            _ngram_path = _DEFAULT_MODEL_PATH.parent / "house_ngram.pkl"
            self.ngram_scorer = HouseNgramScorer.load(_ngram_path)

        self.body   = BodyBuilder(editor, palette)
        self.roof   = RoofBuilder(editor, palette)
        self.detail = DetailBuilder(editor, palette)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, plot: Plot, rotation: int = 0) -> None:
        best_ctx:   Ctx | None = None
        best_score: float      = -1.0

        for _ in range(_MAX_RETRIES):
            ctx      = self._make_context(plot, rotation)
            params   = self._ctx_to_params(ctx)
            rf_score = self.scorer.score(params)

            # Probe block sequence for ngram scoring without touching the world.
            null_recorder = BlockSequenceRecorder(_NullEditor())
            self._place(ctx, editor=null_recorder)
            sequence = null_recorder.finish()

            score = self.ngram_scorer.blend(rf_score, sequence)

            if score > best_score:
                best_score = score
                best_ctx   = ctx
            if score >= self.scorer.threshold:
                break

        logger.debug(
            "HouseGrammar: %dx%d at (%d,%d,%d) score=%.2f roof=%s upper=%s chimney=%s",
            best_ctx.w, best_ctx.d, best_ctx.x, best_ctx.y, best_ctx.z, best_score,
            best_ctx.roof_type, best_ctx.has_upper, best_ctx.has_chimney,
        )
        self._place(best_ctx)

    # ------------------------------------------------------------------
    # Block placement
    # ------------------------------------------------------------------

    def _place(self, ctx: Ctx, editor=None) -> None:
        """
        Place all blocks for a given context.

        Parameters
        ----------
        editor : optional
            If provided, overrides ctx.editor for this build. Pass a
            BlockSequenceRecorder (wrapping a _NullEditor) to probe without
            touching the world. Omit (or pass None) to use the real editor.
        """
        ctx.editor = editor if editor is not None else self.editor
        self.body.build_foundation(ctx)
        self.body.build_body(ctx)
        self.body.build_facade(ctx)
        self.body.build_ceiling(ctx)
        if ctx.has_upper:
            self.body.build_upper(ctx)
        self.roof.build(ctx)
        if ctx.has_chimney:
            self.detail.build_chimney(ctx)
        self.detail.build_interior(ctx)
        self.detail.build_details(ctx)

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _make_context(
        self,
        plot: Plot,
        rotation: int,
        force_bad: bool = False,
    ) -> Ctx:
        """
        Build a Ctx from a plot.

        Parameters
        ----------
        force_bad : bool
            When True, forces structurally distinct bad parameter combinations
            so the eval script can generate sequences that genuinely differ from
            good ones, giving the n-gram model meaningful signal to learn from.
        """
        w, d = plot.width, plot.depth
        if rotation in (90, 270):
            w, d = d, w

        w = max(7, min(w, 11))
        d = max(7, min(d, 11))
        if w % 2 == 0: w -= 1
        if d % 2 == 0: d -= 1

        if force_bad:
            wall_h      = random.choice([3, 5])
            has_upper   = False
            upper_h     = 0
            roof_type   = "cross" if (w < 9 or d < 9) else "gabled"
            has_chimney = False
            has_porch   = False
            door_face   = random.randint(0, 1)
        else:
            wall_h    = random.choice([3, 3, 4])
            has_upper = (w >= 7 and d >= 7 and random.random() < 0.65)
            upper_h   = random.randint(3, 4) if has_upper else 0
            span      = min(w, d)
            if w >= 9 and d >= 9 and random.random() < 0.25:
                roof_type = "cross"
            elif span <= 7 and random.random() < 0.30:
                roof_type = "pyramid"
            else:
                roof_type = "gabled"
            smoke_block = palette_get(self.palette, "smoke", "minecraft:campfire")
            has_chimney = ("campfire" in smoke_block) and (random.random() < 0.80)
            has_porch   = random.random() < 0.45
            door_face   = 0 if random.random() < 0.75 else 1

        return Ctx(
            x=plot.x, y=plot.y, z=plot.z,
            w=w, d=d,
            wall_h=wall_h,
            has_upper=has_upper,
            upper_h=upper_h,
            roof_type=roof_type,
            has_chimney=has_chimney,
            has_porch=has_porch,
            door_face=door_face,
            palette=self.palette,
        )

    def _ctx_to_params(self, ctx: Ctx) -> HouseParams:
        return HouseParams(
            w=ctx.w, d=ctx.d,
            wall_h=ctx.wall_h,
            has_upper=ctx.has_upper,
            upper_h=ctx.upper_h,
            has_chimney=ctx.has_chimney,
            has_porch=ctx.has_porch,
            has_extension=False,
            roof_type=ctx.roof_type if ctx.roof_type in ("gabled", "cross") else "gabled",
            foundation_h=1,
            ext_w=0,
        )


class _NullEditor:
    """
    Discards all placeBlock calls.
    Used as the backing editor for BlockSequenceRecorder during ngram probing,
    so sequences can be scored without touching the world.
    """
    def placeBlock(self, position, block) -> None:
        pass

    def __getattr__(self, name):
        return lambda *a, **kw: None