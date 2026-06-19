# GDMC Settlement Generator

Procedurally generates a coherent medieval settlement in a Minecraft world.
It analyses the terrain, plans districts, roads, and plots, then builds
biome-aware structures into them and writes the result back to the world via
the GDMC HTTP Interface.

For a full module/dependency map see [diagram.mmd](diagram.mmd) (Mermaid), and
for a deeper walkthrough see [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md).

## Requirements

- Python 3.10+
- Minecraft running with the **GDMC HTTP Interface** mod active
- Python deps in [Requirements.txt](Requirements.txt): `gdpc`, `numpy`
  (the `training/` scripts additionally use `pandas`, `scikit-learn`, and
  `matplotlib`)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r Requirements.txt
```

## Run

With Minecraft open and the GDMC HTTP Interface listening:

```bash
python main.py
```

The generator connects, runs the full pipeline, and logs a summary
(districts, road cells, plots, buildings) when finished.

## How it works

`main.py` → `create_generator()` ([generators/__init__.py](generators/__init__.py))
wires the dependencies and hands off to
`SettlementGenerator.generate()`
([generators/settlement_generator.py](generators/settlement_generator.py)),
which runs:

1. **Analyse** the world and pick the best buildable patch (`analysis/`)
2. **Plan districts** as a Voronoi partition, with types assigned by an MDP (`ai/district_mdp.py`)
3. Place a **central plaza + ring road**
4. Place **district markers** (fountains / wells / docks)
5. **Plan and place roads** (MST + A*)
6. **Plan plots** validated against an occupancy map
7. **Build structures** — a weighted selector picks a building per plot, then
   orchestrators → grammar rules → primitive builders construct it (`structures/`)
8. Add **connector footpaths** from each building to the nearest road
9. Build a **perimeter fortification** with corner towers
10. **Flush** the accumulated block buffer to Minecraft

All builders write to an in-memory `BlockBuffer`; a single `StructurePlacer`
performs the actual world writes at the end.

## Project layout

| Path | Purpose |
|------|---------|
| `main.py` | Entry point |
| `generators/` | Composition root + generation pipeline |
| `analysis/` | Terrain fetch, scoring, best-patch selection |
| `ai/` | District-type assignment (MDP via value iteration) |
| `planning/` | District, road, and plot planners |
| `palette/` | Biome/archetype-aware material selection |
| `structures/` | Building generation (selector → orchestrators → grammar → primitives) |
| `data/` | Config, analysis results, settlement state and entities |
| `utils/` | Shared algorithms (A*, MST, Poisson disk, geometry, HTTP client) |
| `world_interface/` | Minecraft I/O: terrain loader, block buffer, placer, terraforming |
| `training/` | Offline ML scripts that produce `models/*.pkl` |
| `models/` | Trained house scorer + n-gram model |
| `debug/` | Standalone manual testers and visualisers |

## House design (ML)

Houses are scored by two trained models in `models/`: a Random Forest shape
scorer and an n-gram block-sequence scorer. For each house the builder samples
several candidate designs and keeps the best-scoring one. Retrain with:

```bash
python training/train_scorer.py      # rescore labels + train RandomForest
python training/eval_house_ngram.py  # train/evaluate the n-gram model
```

## Testing

There is no automated test suite. `debug/test_*.py` are standalone scripts that
build a single structure into a live world; run them from the project root:

```bash
python debug/test_house.py
python debug/test_tavern.py
```
