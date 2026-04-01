# Implementation Notes

## What works
- Settlement planning pipeline: terrain analysis → district Voronoi → road MST/A* → plot placement
- Central plaza placed at best_area centre, ring road around it, districts excluded from plaza zone
- House shape grammar with RF scorer and n-gram aesthetics scorer
- Fortification wall with corner towers around perimeter
- Per-district biome-aware palette
- Terrain cleanup: sparse cluster removal, smoothing, cave sealing

---

## What needs to be implemented

### District-type structures
Each district type should have a dedicated centre decoration placed by `DistrictMarker` based on `district.type`. Currently every district gets the same small fountain regardless of type.

| District type | Suggested centre decoration |
|---|---|
| residential | fountain / well |
| farming | scarecrow or crop field marker |
| fishing | dock post or fishing rack |
| forest | totem pole or stone altar |

`district_marker.py` is the right place — add a type dispatch there.

### Structure coverage per district
Fishing districts currently accept houses and market stalls. They need at least one fishing-specific structure (dock, net hut). `StructureSelector` handles ratios but there is no fishing structure builder yet.

### Structure base class adoption
`Structure` (abstract base) and `StructureAgent` (terrain-aware decision maker) are defined but only `House` inherits from them. The following need adopting before `registry.py` can be the single source of truth:
- `Farm` → inherit `Structure`, implement `build(plot)`
- `Tower` → inherit `Structure`
- `Decoration` → inherit `Structure`
- `Tavern`, `Blacksmith`, `MarketStall`, `ClockTower`, `SpireTower` → inherit `Structure`

Once done, `StructureSelector._load_templates()` can be replaced by `registry.STRUCTURES`.

### Rotation
Most structures accept a `rotation` parameter but ignore it or apply it incorrectly. `BuildContext.push()` handles rotation via GDPC transforms — structures need to pass the correct `origin` and `size` to `BuildContext` and wrap all placement calls inside `ctx.push()`. Currently only `TowerBuilder` does this correctly.

### Terrain levelling per plot
`clear_area()` is called before each structure but only clears vegetation. There is no per-plot terrain levelling — structures on sloped ground will float or clip. A flatten pass (fill low cells up, shave high cells down) is needed per plot before building.

### Post-placement validation
No check is done after a structure is placed to verify it looks correct or didn't clip into terrain. A simple bounding-box air-check would catch the worst cases.

### District centre roads
`RoadPlanner` routes spokes from each district centre to the plaza hub via MST + A*. If the plaza doesn't exist (settlement too small), roads connect district centres directly — which is correct. However the ring road around the plaza has no spoke connections guaranteed to reach it; A* may route past it rather than through it. Consider snapping spoke endpoints to the nearest ring road cell rather than the raw plaza centre.

### Structure variations
Every template always produces the same output. Houses vary via grammar sampling; everything else (tavern, blacksmith, etc.) is deterministic. Adding size or style variants controlled by plot dimensions would improve visual diversity.

### Test coverage
All `debug/test_*.py` files are manual run scripts, not automated tests. Unit tests for planners and builders are missing. Minimum useful coverage:
- `DistrictPlanner.generate()` with a synthetic heightmap
- `RoadPlanner.generate()` with known district centres
- `PlotPlanner.generate()` with a known taken mask
- Individual structure builders (smoke test: does `build()` complete without error)

---

## Structural TODOs (code quality)

- `StructureSelector._load_templates()` creates 9 wrapper objects per instance. Should be a module-level constant once all structures inherit `Structure`.
- `structures/__init__.py`, `structures/tower/__init__.py`, `structures/roofs/` have no `__init__.py` — add exports once the base class adoption above is done.
- `structure_selector.py` mixes template wrappers, a terrain agent (`_QuickAgent`), and selector logic — split into three files once templates are unified via the registry.
