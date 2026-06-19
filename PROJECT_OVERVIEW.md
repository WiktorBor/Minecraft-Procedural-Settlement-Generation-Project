# Project Overview

A GDMC settlement generator: it analyses a Minecraft world, plans districts,
roads, and plots, then procedurally builds structures into them.

See [diagram.mmd](diagram.mmd) for a full module/dependency map, and
[NOTES.md](NOTES.md) for implementation status and known gaps.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r Requirements.txt  # gdpc, numpy
```

Requires Minecraft running with the **GDMC HTTP Interface** mod active.

## Run

```bash
python main.py
```

`main.py` connects to the GDMC HTTP interface, builds a generator via
`create_generator()`, and runs the full pipeline. On success it logs a
settlement summary (districts, road cells, plots, buildings).

## Folder Structure

```
main.py            - Entry point: connect to Minecraft, run the generator
generators/        - Composition root + SettlementGenerator pipeline
analysis/          - Terrain fetch, scoring, and best-patch selection
ai/                - DistrictMDP (district-type assignment via value iteration)
planning/          - District, road, and plot planning
palette/           - Biome/archetype-aware material selection
structures/        - Building generation (selector → orchestrators → grammar → primitives)
data/              - Dataclasses: config, analysis results, settlement state/entities
utils/             - Shared algorithms (A*, MST, Poisson disk, geometry, HTTP client)
world_interface/   - Minecraft I/O: terrain loader, block buffer, placer, terraforming
training/          - Offline ML scripts that produce models/*.pkl (not in runtime path)
models/            - Trained house scorer + n-gram model (.pkl)
debug/             - Standalone manual testers and visualisers
```

## Pipeline (generators/settlement_generator.py)

1. **Analyse** — `WorldAnalyser.prepare()` fetches terrain, scores it, picks the best patch.
2. **District planning** — Voronoi districts, types assigned via `DistrictMDP`.
3. **Plaza + ring road** — civic landmark at the centre (if the area is large enough).
4. **District markers** — fountains / wells / docks per district.
5. **Roads** — MST + A* spokes routed to the hub, placed by `RoadBuilder`.
6. **Plots** — placed and validated against the `OccupancyMap`.
7. **Structures** — `StructureSelector` picks a building per plot from weighted
   district pools; orchestrators → grammar → primitives build it into a `BlockBuffer`.
8. **Connectors** — A* footpaths from each building door to the nearest road.
9. **Fortification** — perimeter wall with corner towers.
10. **Flush** — `StructurePlacer` writes the accumulated `BlockBuffer` to Minecraft.

## Key Files

- [main.py](main.py) — entry point
- [generators/__init__.py](generators/__init__.py) — `create_generator()` composition root
- [generators/settlement_generator.py](generators/settlement_generator.py) — orchestrates the pipeline
- [analysis/world_analysis.py](analysis/world_analysis.py) — terrain analysis
- [planning/settlement_planner.py](planning/settlement_planner.py) — districts/roads/plots
- [palette/palette_system.py](palette/palette_system.py) — material selection
- [structures/structure_selector.py](structures/structure_selector.py) — per-plot building choice
- [structures/house/house.py](structures/house/house.py) — ML-scored procedural houses
- [world_interface/structure_placer.py](world_interface/structure_placer.py) — the only Editor writer

## Testing

There is no automated test suite. `debug/test_*.py` are standalone manual
testers that build a single structure into a live world; run from the project
root, e.g.:

```bash
python debug/test_house.py
python debug/test_tavern.py
```

`debug/visualiser.py` and `debug/district_visualiser.py` render planning output
for inspection.

## ML models

House design uses two trained models in `models/` (a Random Forest shape scorer
and an n-gram block-sequence scorer). Retrain them with the scripts in
`training/`:

```bash
python training/train_scorer.py      # rescore labels + train RandomForest
python training/eval_house_ngram.py  # train/evaluate the n-gram model
```
