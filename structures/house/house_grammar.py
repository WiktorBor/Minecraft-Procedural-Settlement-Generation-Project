"""
structures/house/house_grammar.py
-----------------------------------
Shape grammar for procedural medieval house generation.

    House
      ├── Foundation   cobblestone perimeter + mossy floor
      ├── Body         lower storey walls + windows + top beam
      ├── Facade       door face (door + flanking windows)
      ├── Ceiling      beam ring + slab fill + froglight
      ├── Upper?       half-timbered upper storey walls
      ├── Roof         pyramid | gabled | cross
      ├── Chimney?     cobblestone column + campfire
      ├── Interior     bed, crafting table, pot, vines, moss
      └── Details      lantern, porch, flowers, azalea

Usage
-----
    grammar = HouseGrammar(editor, palette)
    grammar.build(plot, rotation=0)

    # or with raw coordinates (no Plot required):
    grammar.build_at(x, y, z, w, d, rotation=90)
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
from structures.house.house_scorer import HouseParams, HouseScorer
from structures.roofs.roof_builder import build_roof

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"
_MAX_RETRIES        = 4


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

        self.scorer = scorer if scorer is not None else HouseScorer.load(
            model_path if model_path is not None else _DEFAULT_MODEL_PATH
        )
        if ngram_scorer is not None:
            self.ngram_scorer = ngram_scorer
        else:
            _ngram_path = _DEFAULT_MODEL_PATH.parent / "house_ngram.pkl"
            self.ngram_scorer = HouseNgramScorer.load(_ngram_path)

        self.body   = BodyBuilder()
        self.detail = DetailBuilder()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def build(self, plot: Plot, rotation: int = 0) -> None:
        """Build a house on a Plot object."""
        self.build_at(plot.x, plot.y, plot.z, plot.width, plot.depth, rotation)

    def build_at(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        rotation: int = 0,
    ) -> None:
        """
        Build a house at explicit world coordinates.

        Accepts raw (x, y, z, w, d) so callers don't need to construct a Plot.
        Rotation is stored in the context but actual transform support requires
        each builder to go through BuildContext.push() — a future enhancement.
        """
        best_ctx:   Ctx | None = None
        best_score: float      = -1.0

        for _ in range(_MAX_RETRIES):
            ctx    = self._make_context(x, y, z, w, d, rotation)
            params = self._ctx_to_params(ctx)
            rf_score = self.scorer.score(params)

            # Probe block sequence without touching the world
            null_recorder = BlockSequenceRecorder(_NullEditor())
            self._place(ctx, editor_override=null_recorder)
            sequence = null_recorder.finish()

            score = self.ngram_scorer.blend(rf_score, sequence)

            if score > best_score:
                best_score = score
                best_ctx   = ctx
            if score >= self.scorer.threshold:
                break

        logger.debug(
            "HouseGrammar: %dx%d at (%d,%d,%d) score=%.2f roof=%s upper=%s chimney=%s",
            best_ctx.w, best_ctx.d,
            best_ctx.x, best_ctx.y, best_ctx.z,
            best_score, best_ctx.roof_type,
            best_ctx.has_upper, best_ctx.has_chimney,
        )
        self._place(best_ctx)

    # ------------------------------------------------------------------
    # Block placement
    # ------------------------------------------------------------------

    def _place(self, ctx: Ctx, editor_override=None) -> None:
        """
        Place all blocks for the given context.

        Args:
            ctx:             Fully populated Ctx (editor field will be set here).
            editor_override: If provided, replaces ctx.editor for this call.
                             Pass a BlockSequenceRecorder to probe without
                             touching the world.
        """
        # Inject the real editor (or a recorder) into the context
        from dataclasses import replace
        active_ctx = replace(ctx, editor=editor_override if editor_override is not None else self.editor)

        self.body.build_foundation(active_ctx)
        self.body.build_body(active_ctx)
        self.body.build_facade(active_ctx)
        self.body.build_ceiling(active_ctx)
        if active_ctx.has_upper:
            self.body.build_upper(active_ctx)

        build_roof(
            _CtxRoofAdapter(active_ctx),
            active_ctx.x, active_ctx.roof_base_y, active_ctx.z,
            active_ctx.w, active_ctx.d,
            active_ctx.roof_type,
        )

        if active_ctx.has_chimney:
            self.detail.build_chimney(active_ctx)
        self.detail.build_interior(active_ctx)
        self.detail.build_details(active_ctx)

    # ------------------------------------------------------------------
    # Context construction
    # ------------------------------------------------------------------

    def _make_context(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        rotation: int,
        force_bad: bool = False,
    ) -> Ctx:
        """
        Sample grammar parameters and build a Ctx.

        Args:
            force_bad: When True, forces structurally poor combinations so the
                       eval script can generate sequences that genuinely differ
                       from good ones for n-gram training.
        """
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
            wall_h      = random.choice([3, 3, 4])
            has_upper   = (w >= 7 and d >= 7 and random.random() < 0.65)
            upper_h     = random.randint(3, 4) if has_upper else 0
            span        = min(w, d)
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

        # editor is set to self.editor as a placeholder; _place() will override it
        return Ctx(
            x=x, y=y, z=z,
            w=w, d=d,
            wall_h=wall_h,
            has_upper=has_upper,
            upper_h=upper_h,
            roof_type=roof_type,
            has_chimney=has_chimney,
            has_porch=has_porch,
            door_face=door_face,
            palette=self.palette,
            editor=self.editor,
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


# ---------------------------------------------------------------------------
# Null editor for ngram probing
# ---------------------------------------------------------------------------

class _NullEditor:
    """Discards all placeBlock calls — used during ngram sequence probing."""
    def placeBlock(self, position, block) -> None:
        pass
    def __getattr__(self, name):
        return lambda *a, **kw: None


# ---------------------------------------------------------------------------
# Thin adapter so build_roof receives a BuildContext-compatible object
# ---------------------------------------------------------------------------

class _CtxRoofAdapter:
    """
    Makes Ctx compatible with build_roof's BuildContext interface.

    build_roof only needs palette.get(), palette_get(), place_block(),
    and editor.placeBlock() — this adapter provides exactly those.
    """
    def __init__(self, ctx: Ctx) -> None:
        self._ctx = ctx

    @property
    def palette(self):
        return self._ctx.palette

    @property
    def editor(self):
        return self._ctx.editor

    def place_block(self, pos, block):
        self._ctx.editor.placeBlock(pos, block)