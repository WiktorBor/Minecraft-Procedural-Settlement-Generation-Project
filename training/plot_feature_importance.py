"""
plot_feature_importance.py
--------------------------
Loads the trained Random Forest and plots a feature importance bar chart.
Run from the project root:
    python training/plot_feature_importance.py
"""
import pickle
import numpy as np
import matplotlib.pyplot as plt

MODEL_PATH = "models/house_scorer.pkl"

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

feature_names = ["w", "d", "wall_h", "role_num", "roof_num", "upper", "chimney", "porch", "aspect"]
importances = model.feature_importances_
indices = np.argsort(importances)[::-1]

plt.figure(figsize=(8, 5))
plt.bar(range(len(importances)), importances[indices], color="steelblue")
plt.xticks(range(len(importances)), [feature_names[i] for i in indices], rotation=30, ha="right")
plt.ylabel("Importance")
plt.title("Random Forest — Feature Importances (House Scorer)")
plt.tight_layout()
plt.savefig("training/feature_importance.png", dpi=150)
plt.show()
print("Saved to training/feature_importance.png")
