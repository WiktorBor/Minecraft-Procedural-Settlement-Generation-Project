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
    grammar = HouseGrammar(palette)
    buf = grammar.build(plot, rotation=0)    # returns BlockBuffer

    # or with raw coordinates (no Plot required):
    buf = grammar.build_at(x, y, z, w, d, rotation=90)

    # force specific Ctx fields (e.g. for cottage-style cross roofs):
    grammar = HouseGrammar(palette, forced_ctx_overrides={"roof_type": "cross", "cross_side": "west"})
    buf = grammar.build(plot)
"""
from __future__ import annotations

import logging
import random
from dataclasses import replace
from pathlib import Path

from gdpc import Block
from gdpc.transform import rotatedBoxTransform
from gdpc.vector_tools import Box

from palette.palette_system import PaletteSystem, palette_get
from data.settlement_entities import Plot
from structures.house.house_body_builder import BodyBuilder
from structures.house.house_context import Ctx
from structures.house.house_detail_builder import DetailBuilder
from structures.house.house_ngram_scorer import BlockSequenceRecorder, HouseNgramScorer
from structures.house.house_scorer import HouseScorer
from structures.roofs.roof_builder import build_roof
from world_interface.block_buffer import BlockBuffer

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"
_MAX_RETRIES        = 4


class HouseGrammar:

    def __init__(
        self,
        palette: PaletteSystem,
        model_path: Path | None = None,
        scorer: HouseScorer | None = None,
        ngram_scorer: HouseNgramScorer | None = None,
        forced_ctx_overrides: dict | None = None,
    ) -> None:
        self.palette = palette
        self._forced_ctx_overrides: dict = forced_ctx_overrides or {}

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

    @staticmethod
    def effective_footprint(w: int, d: int, rotation: int = 0) -> tuple[int, int]:
        """
        Return the (w, d) the grammar will actually occupy for a given plot
        size and rotation — without running the grammar or scoring.

        Mirrors the dimension clamping in _make_context so callers can
        compute the exact build footprint ahead of time (e.g. for terrain
        leveling).
        """
        if rotation in (90, 270):
            w, d = d, w
        w = max(7, min(w, 11))
        d = max(7, min(d, 11))
        if w % 2 == 0:
            w -= 1
        if d % 2 == 0:
            d -= 1
        return w, d

    def build(self, plot: Plot, rotation: int = 0) -> BlockBuffer:
        """Build a house on a Plot object. Returns a BlockBuffer."""
        return self.build_at(plot.x, plot.y, plot.z, plot.width, plot.depth, rotation)

    def build_at(
        self,
        x: int, y: int, z: int,
        w: int, d: int,
        rotation: int = 0,
    ) -> BlockBuffer:
        """
        Build a house at explicit world coordinates. Returns a BlockBuffer.

        If rotation != 0, builds in axis-aligned local space then rotates
        the buffer's coordinates around the footprint centre.
        """
        best_ctx:   Ctx | None = None
        best_score: float      = -1.0

        for _ in range(_MAX_RETRIES):
            ctx    = self._make_context(x, y, z, w, d, rotation)
            params = self._ctx_to_params(ctx)
            rf_score = self.scorer.score(params)

            # Probe block sequence without touching the world
            recorder = BlockSequenceRecorder()
            probe_ctx = replace(ctx, buffer=recorder)
            self._do_place(probe_ctx)
            sequence = recorder.finish()

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

        # Build into a fresh buffer
        final_ctx = replace(best_ctx, buffer=BlockBuffer())
        self._do_place(final_ctx)
        buf = final_ctx.buffer

        # Apply rotation if needed.
        # Use the internal (swapped + clamped) dimensions that the house was
        # actually built with — NOT the original plot w/d — so the pivot
        # calculation in _rotate_buffer reflects the real footprint size.
        if rotation != 0:
            buf = _rotate_buffer(buf, x, z, best_ctx.w, best_ctx.d, rotation)

        return buf

    # ------------------------------------------------------------------
    # Block placement
    # ------------------------------------------------------------------

    def _do_place(self, ctx: Ctx) -> None:
        """Place all blocks for the given context into ctx.buffer."""
        self.body.build_foundation(ctx)
        self.body.build_body(ctx)
        self.body.build_facade(ctx)
        self.body.build_ceiling(ctx)
        if ctx.has_upper:
            self.body.build_upper(ctx)

        build_roof(
            _CtxRoofAdapter(ctx),
            ctx.x, ctx.roof_base_y, ctx.z,
            ctx.w, ctx.d,
            ctx.roof_type,
            cross_side=ctx.cross_side,
        )

        if ctx.has_chimney:
            self.detail.build_chimney(ctx)
        self.detail.build_interior(ctx)
        self.detail.build_details(ctx)

    # ------------------------------------------------------------------
    # Scorer bridge
    # ------------------------------------------------------------------

    def _ctx_to_params(self, ctx: Ctx):
        """Convert a Ctx to HouseParams for the RF scorer."""
        from structures.house.house_scorer import HouseParams
        return HouseParams(
            w=ctx.w,
            d=ctx.d,
            wall_h=ctx.wall_h,
            has_upper=ctx.has_upper,
            upper_h=ctx.upper_h,
            has_chimney=ctx.has_chimney,
            has_porch=ctx.has_porch,
            has_extension=False,
            roof_type=ctx.roof_type,
            foundation_h=1,
            ext_w=0,
        )

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
        """Sample grammar parameters and build a Ctx."""
        # For east/west plots the footprint is rotated 90° — swap w/d so the
        # local build dimensions match the plot's narrower axis.
        if rotation in (90, 270):
            w, d = d, w

        w = max(7, min(w, 11))
        d = max(7, min(d, 11))
        if w % 2 == 0: w -= 1
        if d % 2 == 0: d -= 1

        door_face = 0   # facade on local north face (low Z) — matches all other builders

        if force_bad:
            wall_h      = random.choice([3, 5])
            has_upper   = False
            upper_h     = 0
            roof_type   = "cross" if (w < 9 or d < 9) else "gabled"
            has_chimney = False
            has_porch   = False
        else:
            wall_h    = random.choice([3, 3, 4])
            has_upper = (w >= 7 and d >= 7 and random.random() < 0.65)
            upper_h   = random.randint(3, 4) if has_upper else 0

            span = min(w, d)
            long = max(w, d)

            if span >= 7 and long >= 9 and random.random() < 0.55:
                roof_type = "cross"
            elif span <= 7 and random.random() < 0.30:
                roof_type = "pyramid"
            else:
                roof_type = "gabled"

            smoke_block = palette_get(self.palette, "smoke", "minecraft:campfire")
            has_chimney = ("campfire" in smoke_block) and (random.random() < 0.80)
            has_porch   = random.random() < 0.45

        ctx = Ctx(
            x=x, y=y, z=z,
            w=w, d=d,
            rotation=rotation,
            wall_h=wall_h,
            has_upper=has_upper,
            upper_h=upper_h,
            roof_type=roof_type,
            cross_side=None,
            has_chimney=has_chimney,
            has_porch=has_porch,
            door_face=door_face,
            palette=self.palette,
            buffer=BlockBuffer(),
        )
        if self._forced_ctx_overrides:
            ctx = replace(ctx, **self._forced_ctx_overrides)
        return ctx


# ---------------------------------------------------------------------------
# Rotation helper — transforms a buffer's coords around the footprint pivot
# ---------------------------------------------------------------------------

def _rotate_buffer(
    buf: BlockBuffer,
    ox: int, oz: int,
    w: int, d: int,
    rotation: int,
) -> BlockBuffer:
    """
    Rotate all block positions and block states in buf by `rotation` degrees
    (0/90/180/270) clockwise around the footprint anchor (ox, oz).

    Uses GDPC's rotatedBoxTransform for coordinate rotation and
    Block.transformed() for block state rotation — same logic as pushTransform.
    """
    steps = (rotation // 90) % 4
    if steps == 0:
        return buf

    # Build the same transform GDPC would use via pushTransform
    box       = Box(offset=(ox, 0, oz), size=(w, 1, d))
    transform = rotatedBoxTransform(box, steps)

    rotated = BlockBuffer()
    for (x, y, z), block in buf.items():
        new_pos = transform.apply((x, y, z))
        rotated.place(int(new_pos[0]), int(new_pos[1]), int(new_pos[2]),
                      block.transformed(transform.rotation, transform.flip))

    return rotated


# ---------------------------------------------------------------------------
# Thin adapter so build_roof receives a BuildContext-compatible object
# ---------------------------------------------------------------------------

class _CtxRoofAdapter:
    """
    Makes Ctx compatible with build_roof's BuildContext interface.
    build_roof only needs palette and place_block().
    """
    def __init__(self, ctx: Ctx) -> None:
        self._ctx = ctx

    @property
    def palette(self):
        return self._ctx.palette

    def place_block(self, pos, block: Block):
        self._ctx.place_block(pos, block)
