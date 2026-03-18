"""
Shape grammar for procedural medieval house generation.

Architecture
------------
A house is assembled from independent grammar rules, each producing one
architectural layer.  Rules are selected randomly within constraints derived
from the plot size and biome palette, so no two houses look identical.

Grammar (top-down):

    House
      ├── Foundation      stone base protruding 1-2 blocks from ground
      ├── Body            lower storey walls (palette wall material)
      ├── UpperStorey?    optional jetty / half-timbered upper floor
      ├── Facade          windows, shutters, door with surround, flower box
      ├── Roof            gabled | hipped | cross-gabled
      ├── Chimney?        optional chimney (never on desert biome)
      └── Details         lantern, fence posts, barrel, optional porch

Each rule is a method on HouseGrammar that writes blocks directly via the
GDPC editor.  All positions are computed in world coordinates from the plot
origin so no coordinate translation is needed at the call site.

Usage
-----
    grammar = HouseGrammar(editor, palette)
    grammar.build(plot, rotation=0)
"""
from __future__ import annotations

import random
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gdpc import Block
from gdpc.editor import Editor

from data.biome_palettes import BiomePalette, palette_get
from data.settlement_entities import Plot
from .house_scorer import HouseScorer, HouseParams

logger = logging.getLogger(__name__)

# Default path the grammar looks for a trained model.
_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "house_scorer.pkl"

# How many parameter sets to try before accepting the best-scoring one.
_MAX_RETRIES = 4


# ---------------------------------------------------------------------------
# Internal build context — computed once per plot, passed between rules
# ---------------------------------------------------------------------------

@dataclass
class _Ctx:
    """All coordinates and dimensions resolved for a single house build."""
    # world origin of the house footprint
    x: int
    y: int
    z: int
    # footprint (may be swapped from plot for rotation)
    w: int
    d: int
    # storey heights
    foundation_h: int   # 1 or 2
    wall_h: int         # lower storey wall height (3-5)
    upper_h: int        # upper storey height (0 = no upper storey)
    # flags
    has_upper: bool
    has_chimney: bool
    has_porch: bool
    has_extension: bool
    # extension dimensions (small lean-to on one side)
    ext_w: int
    ext_d: int
    # facing: which Z face has the door (0 = z_min face, 1 = z_max face)
    door_face: int
    # roof type chosen once so scorer and builder always agree
    roof_type: str   # "gabled" | "steep" | "cross"
    # palette shortcuts
    palette: BiomePalette


# ---------------------------------------------------------------------------
# Main grammar class
# ---------------------------------------------------------------------------

class HouseGrammar:
    """
    Procedural medieval house builder using a shape grammar.

    Replaces HouseBuilder with a richer, more varied result.
    Keeps the same public interface: build(plot, rotation=0).

    If a trained HouseScorer model is found at model_path, the grammar
    will sample up to _MAX_RETRIES parameter sets per house, score each
    one, and build the highest-scoring set that passes the threshold.
    If no model is found the heuristic scorer is used automatically.
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

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self, plot: Plot, rotation: int = 0) -> None:
        """
        Build a house on the given plot with optional 90° rotation steps.

        Samples up to _MAX_RETRIES parameter sets, scores each with the
        aesthetic scorer, and builds the best one.  If none pass the
        threshold after all retries, builds the highest-scoring attempt
        anyway so a house always gets placed.
        """
        best_ctx:   Optional[_Ctx] = None
        best_score: float          = -1.0

        for attempt in range(_MAX_RETRIES):
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
            "HouseGrammar: building %dx%d house at (%d,%d,%d) score=%.2f "
            "upper=%s chimney=%s porch=%s ext=%s",
            ctx.w, ctx.d, ctx.x, ctx.y, ctx.z, best_score,
            ctx.has_upper, ctx.has_chimney, ctx.has_porch, ctx.has_extension,
        )

        self._build_foundation(ctx)
        self._build_body(ctx)
        if ctx.has_upper:
            self._build_upper_storey(ctx)
        self._build_facade(ctx)
        self._build_roof(ctx)
        if ctx.has_chimney:
            self._build_chimney(ctx)
        if ctx.has_extension:
            self._build_extension(ctx)
        self._build_details(ctx)

    # ------------------------------------------------------------------
    # Convert _Ctx → HouseParams for the scorer
    # ------------------------------------------------------------------

    def _ctx_to_params(self, ctx: _Ctx) -> HouseParams:
        """Extract the scorer feature set from a resolved build context."""
        return HouseParams(
            w=ctx.w,
            d=ctx.d,
            wall_h=ctx.wall_h,
            has_upper=ctx.has_upper,
            upper_h=ctx.upper_h,
            has_chimney=ctx.has_chimney,
            has_porch=ctx.has_porch,
            has_extension=ctx.has_extension,
            roof_type=ctx.roof_type,
            foundation_h=ctx.foundation_h,
            ext_w=ctx.ext_w,
        )

    # ------------------------------------------------------------------
    # Context builder — resolve all dimensions and flags from the plot
    # ------------------------------------------------------------------

    def _make_context(self, plot: Plot, rotation: int) -> _Ctx:
        w, d = plot.width, plot.depth
        if rotation in (90, 270):
            w, d = d, w

        # Clamp to sensible house sizes
        w = max(5, min(w, 14))
        d = max(5, min(d, 14))

        foundation_h = random.choice([1, 1, 2])   # usually 1, occasionally 2
        wall_h       = random.randint(3, 5)

        # Upper storey only if footprint is large enough and wall isn't already tall
        has_upper = (w >= 7 and d >= 6 and wall_h <= 4 and random.random() < 0.55)
        upper_h   = random.randint(2, 3) if has_upper else 0

        # Biome-dependent features
        # No chimney if the palette has no fire/smoke (desert uses hay_block)
        smoke_block = palette_get(self.palette, "smoke", "minecraft:campfire")
        has_chimney = ("campfire" in smoke_block) and (random.random() < 0.75)
        has_porch     = (w >= 7) and (random.random() < 0.40)
        has_extension = (w >= 8 and d >= 8) and (random.random() < 0.35)

        # Extension: small lean-to on the back (z_max side)
        ext_w = random.randint(3, max(3, w // 2)) if has_extension else 0
        ext_d = random.randint(2, 3)               if has_extension else 0

        door_face = 0 if random.random() < 0.75 else 1

        # Roof type — decided once here so scorer and builder are consistent.
        # Cross-gabled only on large square-ish footprints.
        span = min(w, d)   # shorter axis drives pitch
        if w >= 9 and d >= 9 and random.random() < 0.20:
            roof_type = "cross"
        elif span <= 7 and random.random() < 0.35:
            roof_type = "steep"
        else:
            roof_type = "gabled"

        return _Ctx(
            x=plot.x, y=plot.y, z=plot.z,
            w=w, d=d,
            foundation_h=foundation_h,
            wall_h=wall_h,
            upper_h=upper_h,
            has_upper=has_upper,
            has_chimney=has_chimney,
            has_porch=has_porch,
            has_extension=has_extension,
            ext_w=ext_w,
            ext_d=ext_d,
            door_face=door_face,
            roof_type=roof_type,
            palette=self.palette,
        )

    # ------------------------------------------------------------------
    # Grammar rules
    # ------------------------------------------------------------------

    def _build_foundation(self, ctx: _Ctx) -> None:
        """
        Stone foundation perimeter visible at ground level, plus solid fill
        below ground so the building looks embedded rather than floating.
        Only the perimeter course is placed at ctx.y — the interior at that
        level is left for _build_body to fill with the floor material.
        """
        mat = ctx.palette["foundation"]

        positions = []
        # Below-ground fill (solid, all cells)
        for dy in range(-ctx.foundation_h, 0):
            for dx in range(ctx.w):
                for dz in range(ctx.d):
                    positions.append((ctx.x + dx, ctx.y + dy, ctx.z + dz))

        # Ground-level foundation course — perimeter only so the interior
        # stays clear for the floor block placed by _build_body.
        for dx in range(ctx.w):
            positions.append((ctx.x + dx, ctx.y, ctx.z))
            positions.append((ctx.x + dx, ctx.y, ctx.z + ctx.d - 1))
        for dz in range(1, ctx.d - 1):
            positions.append((ctx.x,             ctx.y, ctx.z + dz))
            positions.append((ctx.x + ctx.w - 1, ctx.y, ctx.z + dz))

        self.editor.placeBlock(positions, Block(mat))

    def _build_body(self, ctx: _Ctx) -> None:
        """
        Lower storey: solid floor + hollow walls.
        ctx.y        = foundation top / ground level (foundation material)
        ctx.y + 1    = floor (floor material, interior only)
        ctx.y + 2 .. ctx.y + wall_h = walls (inclusive both ends)
        """
        mat_wall  = ctx.palette["wall"]
        mat_floor = ctx.palette["floor"]
        base_y    = ctx.y + 1      # floor level

        # Interior floor (inside the foundation perimeter)
        floor_pos = [
            (ctx.x + dx, base_y, ctx.z + dz)
            for dx in range(1, ctx.w - 1)
            for dz in range(1, ctx.d - 1)
        ]
        self.editor.placeBlock(floor_pos, Block(mat_floor))

        # Hollow walls from base_y+1 up to and including base_y+wall_h
        wall_pos = []
        for dy in range(1, ctx.wall_h + 1):
            y = base_y + dy
            for dx in range(ctx.w):
                wall_pos.append((ctx.x + dx,            y, ctx.z))
                wall_pos.append((ctx.x + dx,            y, ctx.z + ctx.d - 1))
            for dz in range(1, ctx.d - 1):
                wall_pos.append((ctx.x,                 y, ctx.z + dz))
                wall_pos.append((ctx.x + ctx.w - 1,     y, ctx.z + dz))
        self.editor.placeBlock(wall_pos, Block(mat_wall))

    def _build_upper_storey(self, ctx: _Ctx) -> None:
        """
        Half-timbered upper storey with a 1-block jetty overhang on the
        front face (z_min side).

        Y layout (relative to ctx.y):
          ctx.y + 1 + wall_h      = jetty slab row (top of lower walls)
          ctx.y + 1 + wall_h + 1  = first upper wall row
          ...
          ctx.y + 1 + wall_h + upper_h = last upper wall row (roof starts here)
        """
        mat_wall   = ctx.palette["wall"]
        mat_accent = ctx.palette["accent"]
        mat_floor  = ctx.palette["floor"]
        mat_slab   = palette_get(ctx.palette, "slab", "minecraft:cobblestone_slab")

        # Jetty slab sits one above the last wall row of the lower storey
        jetty_y  = ctx.y + 1 + ctx.wall_h + 1
        upper_y  = jetty_y          # upper walls start at same Y as jetty slab

        # --- Jetty slab row ---
        # Main footprint + 1-block overhang on front face only
        jetty_pos = []
        front_z = ctx.z if ctx.door_face == 0 else ctx.z + ctx.d - 1
        overhang_z = front_z - 1 if ctx.door_face == 0 else front_z + 1
        for dx in range(ctx.w):
            jetty_pos.append((ctx.x + dx, jetty_y, overhang_z))
        for dx in range(ctx.w):
            for dz in range(ctx.d):
                jetty_pos.append((ctx.x + dx, jetty_y, ctx.z + dz))
        self.editor.placeBlock(jetty_pos, Block(mat_slab, {"type": "bottom"}))

        # --- Half-timbered upper walls ---
        # Start one above the jetty slab so there is no gap
        wall_pos_plank  = []
        wall_pos_accent = []

        for dy in range(1, ctx.upper_h + 1):
            y = upper_y + dy
            is_rail = (dy % 2 == 0)

            for dx in range(ctx.w):
                is_post = (dx == 0 or dx == ctx.w - 1)
                block = mat_accent if (is_post or is_rail) else mat_wall
                lst = wall_pos_accent if block == mat_accent else wall_pos_plank
                lst.append((ctx.x + dx, y, ctx.z))
                lst.append((ctx.x + dx, y, ctx.z + ctx.d - 1))

            for dz in range(1, ctx.d - 1):
                is_post = False   # side-face interior, no corner post
                block = mat_accent if is_rail else mat_wall
                lst = wall_pos_accent if block == mat_accent else wall_pos_plank
                lst.append((ctx.x,             y, ctx.z + dz))
                lst.append((ctx.x + ctx.w - 1, y, ctx.z + dz))

        if wall_pos_plank:
            self.editor.placeBlock(wall_pos_plank,  Block(mat_wall))
        if wall_pos_accent:
            self.editor.placeBlock(wall_pos_accent, Block(mat_accent))

    def _build_facade(self, ctx: _Ctx) -> None:
        """
        Place door (with stone surround), windows (with shutters), and
        an optional flower box on the front face.
        """
        mat_window  = palette_get(ctx.palette, "window", "minecraft:glass_pane")
        mat_door    = palette_get(ctx.palette, "door",   "minecraft:oak_door")
        mat_accent  = ctx.palette["accent"]
        mat_floor   = ctx.palette["floor"]
        mat_slab    = palette_get(ctx.palette, "slab", "minecraft:cobblestone_slab")

        base_y = ctx.y + 1   # floor level

        # Choose front face Z
        face_z  = ctx.z if ctx.door_face == 0 else ctx.z + ctx.d - 1
        facing  = "south" if ctx.door_face == 0 else "north"

        # --- Door ---
        door_x = ctx.x + ctx.w // 2
        mat_slab_door = palette_get(ctx.palette, "slab", "minecraft:cobblestone_slab")

        # Clear the two door blocks (place air), then door on top
        self.editor.placeBlock((door_x, base_y + 1, face_z), Block("minecraft:air"))
        self.editor.placeBlock((door_x, base_y + 2, face_z), Block("minecraft:air"))

        # Lintel above door using palette slab
        self.editor.placeBlock(
            (door_x, base_y + 3, face_z),
            Block(mat_slab_door, {"type": "bottom"}),
        )

        # Door blocks (lower + upper half)
        self.editor.placeBlock(
            (door_x, base_y + 1, face_z),
            Block(mat_door, {"facing": facing, "half": "lower", "hinge": "left"}),
        )
        self.editor.placeBlock(
            (door_x, base_y + 2, face_z),
            Block(mat_door, {"facing": facing, "half": "upper", "hinge": "left"}),
        )

        # --- Windows on front face ---
        # Windows sit at wall_h - 1 from base so they're mid-wall.
        # win_y is chosen so there is one wall block above AND below the pane.
        win_y = base_y + 2   # 1 above floor, leaving 1 wall block above
        win_positions = []
        if ctx.w >= 7:
            # Two windows flanking door, 2 blocks either side
            for wx in [door_x - 2, door_x + 2]:
                if ctx.x < wx < ctx.x + ctx.w - 1:  # must be inside wall
                    win_positions.append((wx, win_y, face_z))
        elif ctx.w >= 5:
            # One window each side of door
            for wx in [door_x - 1, door_x + 1]:
                if ctx.x < wx < ctx.x + ctx.w - 1:
                    win_positions.append((wx, win_y, face_z))

        # Place glass panes — they connect to adjacent wall blocks naturally
        if win_positions:
            self.editor.placeBlock(win_positions, Block(mat_window))

        # Lintel slab above each window — "bottom" type so it hangs from
        # the ceiling of the block above, not sits on the floor.
        lintel_pos = [(wx, win_y + 1, wz) for wx, _, wz in win_positions]
        if lintel_pos:
            self.editor.placeBlock(lintel_pos, Block(mat_slab, {"type": "bottom"}))

        # Sill slab below each window — "top" type so it sits on the floor
        # of the window block, acting as a window sill.
        sill_pos = [(wx, win_y - 1, wz) for wx, _, wz in win_positions]
        if sill_pos:
            self.editor.placeBlock(sill_pos, Block(mat_slab, {"type": "top"}))

        # --- Windows on side faces (mid-depth, one block in from corners) ---
        side_y = base_y + 2
        mid_z  = ctx.z + ctx.d // 2
        side_win = []
        if ctx.d >= 7:
            side_win += [
                (ctx.x,             side_y, mid_z),
                (ctx.x + ctx.w - 1, side_y, mid_z),
            ]
        if side_win:
            self.editor.placeBlock(side_win, Block(mat_window))

    def _build_roof(self, ctx: _Ctx) -> None:
        """
        Dispatch to the correct roof builder using the type already chosen
        in _make_context.  No re-rolling here — the scorer and the builder
        always see the same roof_type.
        """
        if ctx.roof_type == "cross":
            self._roof_cross_gabled(ctx)
        elif ctx.roof_type == "steep":
            self._roof_gabled(ctx, steep=True)
        else:
            self._roof_gabled(ctx, steep=False)

    def _roof_gabled(self, ctx: _Ctx, steep: bool = False) -> None:
        """
        Gabled roof that adapts to the building footprint.

        The ridge always runs along the LONGER axis so the pitch is driven
        by the SHORTER axis — exactly how real pitched roofs work.

        If w >= d:  ridge runs along Z (depth), stairs face east/west.
        If d >  w:  ridge runs along X (width), stairs face south/north.
        """
        mat_roof   = ctx.palette["roof"]
        mat_accent = ctx.palette["accent"]
        roof_slab  = palette_get(ctx.palette, "slab", "minecraft:cobblestone_slab")
        win_mat    = palette_get(ctx.palette, "window", "minecraft:glass_pane")

        if ctx.has_upper:
            base_y = ctx.y + 1 + ctx.wall_h + 1 + ctx.upper_h + 1
        else:
            base_y = ctx.y + 1 + ctx.wall_h + 1

        # Choose pitch axis: shorter dimension drives peak height
        pitch_along_x = (ctx.w <= ctx.d)   # True = stairs face E/W, ridge along Z
        span   = ctx.w if pitch_along_x else ctx.d    # the dimension being spanned
        length = ctx.d if pitch_along_x else ctx.w    # the ridge length

        peak = (span // 2) + (1 if steep else 0)

        for layer in range(peak):
            for along in range(length):
                if pitch_along_x:
                    # Left slope (west-facing stair on east side, east-facing on west)
                    self.editor.placeBlock(
                        (ctx.x + layer, base_y + layer, ctx.z + along),
                        Block(mat_roof, {"facing": "east"}),
                    )
                    self.editor.placeBlock(
                        (ctx.x + ctx.w - 1 - layer, base_y + layer, ctx.z + along),
                        Block(mat_roof, {"facing": "west"}),
                    )
                else:
                    # Ridge along X — stairs face south/north
                    self.editor.placeBlock(
                        (ctx.x + along, base_y + layer, ctx.z + layer),
                        Block(mat_roof, {"facing": "south"}),
                    )
                    self.editor.placeBlock(
                        (ctx.x + along, base_y + layer, ctx.z + ctx.d - 1 - layer),
                        Block(mat_roof, {"facing": "north"}),
                    )

        # Ridge cap for odd span
        if span % 2 == 1:
            ridge_y = base_y + peak - 1
            if pitch_along_x:
                ridge_mid = ctx.x + span // 2
                ridge_pos = [
                    (ridge_mid, ridge_y, ctx.z + along)
                    for along in range(length)
                ]
            else:
                ridge_mid = ctx.z + span // 2
                ridge_pos = [
                    (ctx.x + along, ridge_y, ridge_mid)
                    for along in range(length)
                ]
            self.editor.placeBlock(ridge_pos, Block(roof_slab, {"type": "top"}))

        # Gable-end accent logs — on the two SHORT faces (the triangular ends)
        if span >= 5:
            if pitch_along_x:
                # Gable ends face Z (front and back)
                gable_faces = [ctx.z, ctx.z + ctx.d - 1]
                mid = ctx.x + span // 2
                for gz in gable_faces:
                    for gx in range(mid - 2, mid + 3):
                        if ctx.x <= gx < ctx.x + ctx.w:
                            self.editor.placeBlock((gx, base_y, gz), Block(mat_accent))
                    for gx in (mid - 1, mid + 1):
                        if ctx.x <= gx < ctx.x + ctx.w:
                            self.editor.placeBlock((gx, base_y + 1, gz), Block(mat_accent))
            else:
                # Gable ends face X (left and right sides)
                gable_faces = [ctx.x, ctx.x + ctx.w - 1]
                mid = ctx.z + span // 2
                for gx in gable_faces:
                    for gz in range(mid - 2, mid + 3):
                        if ctx.z <= gz < ctx.z + ctx.d:
                            self.editor.placeBlock((gx, base_y, gz), Block(mat_accent))
                    for gz in (mid - 1, mid + 1):
                        if ctx.z <= gz < ctx.z + ctx.d:
                            self.editor.placeBlock((gx, base_y + 1, gz), Block(mat_accent))

        # Gable window in the triangular end
        if peak >= 2:
            if pitch_along_x:
                wx_ = ctx.x + span // 2
                for fz in (ctx.z, ctx.z + ctx.d - 1):
                    self.editor.placeBlock((wx_, base_y + 1, fz), Block(win_mat))
            else:
                wz_ = ctx.z + span // 2
                for fx in (ctx.x, ctx.x + ctx.w - 1):
                    self.editor.placeBlock((fx, base_y + 1, wz_), Block(win_mat))

    def _roof_cross_gabled(self, ctx: _Ctx) -> None:
        """
        Cross-gabled roof: two intersecting gabled ridges.
        Each arm pitches from its own shorter span.
        Only triggered for large footprints (w >= 9, d >= 9).
        """
        mat_roof  = ctx.palette["roof"]
        roof_slab = palette_get(ctx.palette, "slab", "minecraft:cobblestone_slab")

        if ctx.has_upper:
            base_y = ctx.y + 1 + ctx.wall_h + 1 + ctx.upper_h + 1
        else:
            base_y = ctx.y + 1 + ctx.wall_h + 1

        # X-axis pitch (stairs face E/W), ridge runs along Z
        peak_x = ctx.w // 2
        for layer in range(peak_x):
            for dz in range(ctx.d):
                self.editor.placeBlock(
                    (ctx.x + layer,             base_y + layer, ctx.z + dz),
                    Block(mat_roof, {"facing": "east"}),
                )
                self.editor.placeBlock(
                    (ctx.x + ctx.w - 1 - layer, base_y + layer, ctx.z + dz),
                    Block(mat_roof, {"facing": "west"}),
                )

        # Z-axis pitch (stairs face S/N), ridge runs along X — overlaps at peak
        peak_z = ctx.d // 2
        for layer in range(peak_z):
            for dx in range(ctx.w):
                self.editor.placeBlock(
                    (ctx.x + dx, base_y + layer, ctx.z + layer),
                    Block(mat_roof, {"facing": "south"}),
                )
                self.editor.placeBlock(
                    (ctx.x + dx, base_y + layer, ctx.z + ctx.d - 1 - layer),
                    Block(mat_roof, {"facing": "north"}),
                )

    def _build_chimney(self, ctx: _Ctx) -> None:
        """
        Chimney in a back corner, rising 2 blocks above the roof peak.
        Uses foundation material (stone/cobblestone).
        """
        mat = ctx.palette["foundation"]

        if ctx.has_upper:
            roof_base = ctx.y + 1 + ctx.wall_h + 1 + ctx.upper_h + 1
        else:
            roof_base = ctx.y + 1 + ctx.wall_h + 1

        roof_peak = roof_base + min(ctx.w, ctx.d) // 2 + 2  # 2 above roof peak

        # Alternate between back-left and back-right corner
        cx = ctx.x + (ctx.w - 2 if random.random() < 0.5 else 1)
        cz = ctx.z + ctx.d - 2

        pos = [(cx, y, cz) for y in range(ctx.y + 1, roof_peak + 1)]
        self.editor.placeBlock(pos, Block(mat))

        # Smoke effect at chimney top — campfire gets lit=true, hay bale gets none
        mat_smoke   = palette_get(ctx.palette, "smoke", "minecraft:campfire")
        smoke_props = {"lit": "true", "signal_fire": "false", "facing": "north"} if "campfire" in mat_smoke else {}
        self.editor.placeBlock((cx, roof_peak + 1, cz), Block(mat_smoke, smoke_props))

    def _build_extension(self, ctx: _Ctx) -> None:
        """
        Small lean-to extension on the back of the house — a lower single-storey
        room that breaks up the rectangular silhouette.
        """
        mat_wall  = ctx.palette["wall"]
        mat_floor = ctx.palette["floor"]
        mat_roof  = ctx.palette["roof"]
        mat_found = ctx.palette["foundation"]

        # Position: centred on back face (z_max), protruding outward
        x_off  = (ctx.w - ctx.ext_w) // 2
        ext_x  = ctx.x + x_off
        ext_z  = ctx.z + ctx.d          # starts just past the house back wall
        ext_y  = ctx.y + 1
        ext_h  = 3                       # lean-to is shorter than main body

        # Foundation
        found_pos = [
            (ext_x + dx, ext_y - 1, ext_z + dz)
            for dx in range(ctx.ext_w)
            for dz in range(ctx.ext_d)
        ]
        self.editor.placeBlock(found_pos, Block(mat_found))

        # Floor
        floor_pos = [
            (ext_x + dx, ext_y, ext_z + dz)
            for dx in range(ctx.ext_w)
            for dz in range(ctx.ext_d)
        ]
        self.editor.placeBlock(floor_pos, Block(mat_floor))

        # Walls (hollow box)
        wall_pos = []
        for dy in range(1, ext_h):
            y = ext_y + dy
            for dx in range(ctx.ext_w):
                wall_pos.append((ext_x + dx, y, ext_z))
                wall_pos.append((ext_x + dx, y, ext_z + ctx.ext_d - 1))
            for dz in range(ctx.ext_d):
                wall_pos.append((ext_x,                  y, ext_z + dz))
                wall_pos.append((ext_x + ctx.ext_w - 1,  y, ext_z + dz))
        self.editor.placeBlock(wall_pos, Block(mat_wall))

        # Lean-to roof: single slope (all facing outward)
        roof_slab = palette_get(ctx.palette, "slab", "minecraft:cobblestone_slab")
        for dz in range(ctx.ext_d):
            self.editor.placeBlock(
                (ext_x,                 ext_y + ext_h,     ext_z + dz),
                Block(mat_roof, {"facing": "east"}),
            )
            self.editor.placeBlock(
                (ext_x + ctx.ext_w - 1, ext_y + ext_h,     ext_z + dz),
                Block(mat_roof, {"facing": "west"}),
            )
        # Flat cap in the middle
        if ctx.ext_w > 2:
            cap_pos = [
                (ext_x + dx, ext_y + ext_h, ext_z + dz)
                for dx in range(1, ctx.ext_w - 1)
                for dz in range(ctx.ext_d)
            ]
            self.editor.placeBlock(cap_pos, Block(roof_slab, {"type": "top"}))

    def _build_details(self, ctx: _Ctx) -> None:
        """
        Decorative details placed either outside (in front of the wall) or
        inside (behind the wall face) — never IN the wall itself.

        Outside: lantern on wall above door, porch posts, barrels beside door.
        Inside:  crafting table or chest as interior furniture.
        """
        mat_light  = palette_get(ctx.palette, "light",  "minecraft:lantern")
        mat_accent = ctx.palette["accent"]
        mat_found  = ctx.palette["foundation"]

        base_y = ctx.y + 1
        # face_z is the wall block — outside is one step beyond it
        face_z    = ctx.z if ctx.door_face == 0 else ctx.z + ctx.d - 1
        outside_z = face_z + (-1 if ctx.door_face == 0 else 1)  # 1 block in front
        inside_z  = face_z + (1  if ctx.door_face == 0 else -1)  # 1 block inside
        door_x    = ctx.x + ctx.w // 2

        # --- Lantern: mounted ON the wall face, above the door ---
        # Placed against the wall block (face_z), not in empty space.
        light_props = {"hanging": "false"} if "lantern" in mat_light else {}
        self.editor.placeBlock(
            (door_x, base_y + 3, face_z),
            Block(mat_light, light_props),
        )

        # --- Porch: fence posts and slab floor OUTSIDE (beyond face_z) ---
        if ctx.has_porch:
            fence = palette_get(ctx.palette, "fence", "minecraft:oak_fence")
            slab  = palette_get(ctx.palette, "slab", "minecraft:cobblestone_slab")
            # Slab step directly outside the door
            self.editor.placeBlock(
                [(door_x + dx, base_y, outside_z) for dx in range(-1, 2)],
                Block(slab, {"type": "bottom"}),
            )
            # Fence posts flanking the step
            self.editor.placeBlock(
                [(door_x - 1, base_y,     outside_z),
                 (door_x - 1, base_y + 1, outside_z),
                 (door_x + 1, base_y,     outside_z),
                 (door_x + 1, base_y + 1, outside_z)],
                Block(fence),
            )

        # --- Barrels: placed OUTSIDE the front wall, beside the door ---
        if random.random() < 0.6:
            mat_prop    = palette_get(ctx.palette, "prop", "minecraft:barrel")
            prop_props  = {"facing": "up"} if "barrel" in mat_prop else {}
            side_offset = random.choice([-2, 2])
            barrel_x    = door_x + side_offset
            barrel_x    = max(ctx.x + 1, min(ctx.x + ctx.w - 2, barrel_x))
            self.editor.placeBlock(
                (barrel_x, base_y, outside_z),
                Block(mat_prop, prop_props),
            )
            if random.random() < 0.4:
                barrel_x2 = door_x - side_offset
                barrel_x2 = max(ctx.x + 1, min(ctx.x + ctx.w - 2, barrel_x2))
                self.editor.placeBlock(
                    (barrel_x2, base_y, outside_z),
                    Block(mat_prop, prop_props),
                )

        # --- Interior furniture: placed INSIDE, away from the door ---
        # Only place if the interior is deep enough to have space
        if ctx.d >= 6:
            furniture = random.choice([
                ("minecraft:crafting_table", {}),
                ("minecraft:chest", {"facing": "south"}),
                ("minecraft:bookshelf", {}),
                ("minecraft:furnace", {"facing": "south", "lit": "false"}),
            ])
            fur_x = ctx.x + random.randint(1, ctx.w - 2)
            fur_z = inside_z + (1 if ctx.door_face == 0 else -1)
            # Keep furniture inside the footprint
            fur_z = max(ctx.z + 1, min(ctx.z + ctx.d - 2, fur_z))
            self.editor.placeBlock(
                (fur_x, base_y + 1, fur_z),
                Block(furniture[0], furniture[1]),
            )
