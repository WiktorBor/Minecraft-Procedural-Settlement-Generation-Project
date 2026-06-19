import random
from collections import Counter

# ---- INPUT: Replace this with your generated palettes ----
# Example format: list of palette dicts returned by your system
# Each palette must contain at least: archetype, wall, frame, roof_block

sample_palettes = [
    {"archetype": "TEMPERATE", "wall": "minecraft:stone_bricks", "frame": "minecraft:oak_log", "roof_block": "minecraft:dark_oak_planks"},
    {"archetype": "TEMPERATE", "wall": "minecraft:cobblestone", "frame": "minecraft:oak_log", "roof_block": "minecraft:dark_oak_planks"},
    {"archetype": "FROZEN", "wall": "minecraft:deepslate_bricks", "frame": "minecraft:spruce_log", "roof_block": "minecraft:spruce_planks"},
]

# ---- METRIC 1: Material Diversity ----
def material_diversity(palettes):
    materials = [p["wall"] for p in palettes]
    unique = len(set(materials))
    total = len(materials)
    return unique / total if total > 0 else 0

# ---- METRIC 2: Anti-Clustering ----
def anti_clustering_score(palettes):
    materials = [p["wall"] for p in palettes]
    repeats = 0
    for i in range(1, len(materials)):
        if materials[i] == materials[i - 1]:
            repeats += 1
    return repeats / len(materials) if materials else 0

# ---- METRIC 3: Environmental Consistency ----
EXPECTED = {
    "TEMPERATE": ["stone", "oak"],
    "FROZEN": ["deepslate", "spruce"],
    "ARID": ["sandstone", "acacia"],
    "LUSH": ["moss", "jungle"],
    "AQUATIC": ["prismarine"],
    "SAVANNA": ["terracotta", "acacia"],
}

def environmental_consistency(palettes):
    correct = 0
    for p in palettes:
        archetype = p["archetype"]
        wall = p["wall"]
        expected_keywords = EXPECTED.get(archetype, [])
        if any(keyword in wall for keyword in expected_keywords):
            correct += 1
    return correct / len(palettes) if palettes else 0

# ---- METRIC 4: Palette Coherence ----
def palette_coherence(palettes):
    coherent = 0
    for p in palettes:
        frame = p["frame"]
        roof = p["roof_block"]

        # crude check: same wood family keyword
        if frame.split(":")[-1].split("_")[0] in roof:
            coherent += 1

    return coherent / len(palettes) if palettes else 0

# ---- METRIC 5: Weight Distribution Accuracy ----
def weight_accuracy(palettes, expected_weights):
    materials = [p["wall"].replace("minecraft:", "") for p in palettes]
    counts = Counter(materials)
    total = len(materials)

    error = 0
    for mat, expected in expected_weights.items():
        actual = counts.get(mat, 0) / total if total > 0 else 0
        error += abs(expected - actual)

    return error

# Example expected weights (adjust per archetype when testing properly)
EXPECTED_WEIGHTS = {
    "stone_bricks": 0.6,
    "cobblestone": 0.3,
    "andesite": 0.1
}

# ---- RUN ALL METRICS ----
def evaluate(palettes):
    results = {
        "Material Diversity": material_diversity(palettes),
        "Anti-Clustering": anti_clustering_score(palettes),
        "Environmental Consistency": environmental_consistency(palettes),
        "Palette Coherence": palette_coherence(palettes),
        "Weight Error": weight_accuracy(palettes, EXPECTED_WEIGHTS)
    }
    return results


if __name__ == "__main__":
    results = evaluate(sample_palettes)

    print("\n--- Evaluation Results ---")
    for k, v in results.items():
        print(f"{k}: {v:.3f}")
