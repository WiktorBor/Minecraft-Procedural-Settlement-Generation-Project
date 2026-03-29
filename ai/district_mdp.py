"""
district_mdp.py
---------------
MDP-based district type assignment via value iteration.

Solves a tabular MDP over a small, fully enumerable state space
(27 states × 4 actions) where each state encodes discretised terrain
features (slope, roughness, water distance) and each action is a district
type (fishing, farming, residential, forest).

The MDP is solved once at DistrictPlanner construction time —
O(27 × 4 × iterations) work, negligible compared to the Voronoi computation.
DistrictPlanner calls _assign_type(), which delegates to DistrictMDP.act().

Public API
----------
DistrictMDP
    Solver and inference engine.

thresholds_from_terrain(slope_map, roughness_map, config)
    Derive bin thresholds from actual terrain percentiles.
    Preferred at runtime — adapts to the true world distribution.

thresholds_from_config(config)
    Derive bin thresholds from SettlementConfig values alone.
    Useful for testing without a real terrain map.

Threshold derivation
--------------------
Bin boundaries split each feature into three ranges (low / mid / high).
thresholds_from_terrain() anchors them to the 33rd / 66th percentiles of
the actual world data so bins always reflect the true terrain distribution
rather than hand-tuned constants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from data.configurations import SettlementConfig


# ---------------------------------------------------------------------------
# Threshold helpers
# ---------------------------------------------------------------------------

def thresholds_from_terrain(
    slope_map:     np.ndarray,
    roughness_map: np.ndarray,
    config:        "SettlementConfig",
) -> dict[str, tuple[float, float]]:
    """
    Derive MDP bin thresholds from actual terrain percentiles.

    Anchors slope and roughness bins to the 33rd / 66th percentiles of
    the world data so the three bins always reflect the true distribution.
    Water thresholds remain anchored to SettlementConfig so the fishing
    district constraint is consistent with the rest of the planner.

    Returns
    -------
    dict with keys: slope_thresholds, roughness_thresholds, water_thresholds
    Each value is a (low, high) float tuple.
    """
    s_low, s_high = np.percentile(slope_map,     [33.3, 66.6])
    r_low, r_high = np.percentile(roughness_map, [33.3, 66.6])

    water_low = float(
        config.district_type_rules.get("fishing", {}).get("water_dist_max", 10.0)
    )

    return {
        "slope_thresholds":     (max(0.1, float(s_low)), max(0.2, float(s_high))),
        "roughness_thresholds": (max(0.1, float(r_low)), max(0.2, float(r_high))),
        "water_thresholds":     (water_low, water_low * 3),
    }


def thresholds_from_config(
    config: "SettlementConfig",
) -> dict[str, tuple[float, float]]:
    """
    Derive MDP bin thresholds from SettlementConfig values alone.

    Bin logic (same for all three features):
        value <= low_thresh              → bin 0  (low / favourable)
        low_thresh < value < high_thresh → bin 1  (mid)
        value >= high_thresh             → bin 2  (high / unfavourable)

    Derivation
    ----------
    slope
        low  = farming slope_max           (flat enough for crops)
        high = SettlementConfig.max_slope × 3  (well above plot placement limit)

    roughness
        low  = farming roughness_max / 2   (smooth enough for crops)
        high = SettlementConfig.max_roughness  (at the plot placement hard limit)

    water distance
        low  = fishing water_dist_max      (close enough for a fishing village)
        high = fishing water_dist_max × 3  (far enough to rule out fishing)
    """
    farming_rules = config.district_type_rules.get("farming", {})
    fishing_rules = config.district_type_rules.get("fishing", {})

    slope_low  = float(farming_rules.get("slope_max",     3.0))
    slope_high = float(config.max_slope) * 3

    rough_low  = float(farming_rules.get("roughness_max", 8.0)) / 2
    rough_high = float(config.max_roughness)

    water_low  = float(fishing_rules.get("water_dist_max", 10.0))
    water_high = water_low * 3

    return {
        "slope_thresholds":     (slope_low,  slope_high),
        "roughness_thresholds": (rough_low,  rough_high),
        "water_thresholds":     (water_low,  water_high),
    }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# District types in a fixed order so array indices are stable.
ACTIONS: list[str] = ["fishing", "farming", "residential", "forest"]
ACTION_INDEX: dict[str, int] = {a: i for i, a in enumerate(ACTIONS)}

N_BINS    = 3              # bins per feature: 0=low, 1=mid, 2=high
N_STATES  = N_BINS ** 3   # 27 states
N_ACTIONS = len(ACTIONS)  # 4 actions


# ---------------------------------------------------------------------------
# State encoding / decoding
# ---------------------------------------------------------------------------

def state_index(slope_bin: int, roughness_bin: int, water_bin: int) -> int:
    """Encode (slope_bin, roughness_bin, water_bin) → flat state index 0..26."""
    return slope_bin * N_BINS ** 2 + roughness_bin * N_BINS + water_bin


def decode_state(idx: int) -> tuple[int, int, int]:
    """Decode flat state index → (slope_bin, roughness_bin, water_bin)."""
    slope_bin     = idx // (N_BINS ** 2)
    remainder     = idx %  (N_BINS ** 2)
    roughness_bin = remainder // N_BINS
    water_bin     = remainder %  N_BINS
    return slope_bin, roughness_bin, water_bin


def discretise(value: float, low_thresh: float, high_thresh: float) -> int:
    """
    Map a continuous value to a 3-bin discrete index.

    value <= low_thresh  → 0 (low)
    value >= high_thresh → 2 (high)
    otherwise            → 1 (mid)
    """
    if value <= low_thresh:
        return 0
    if value >= high_thresh:
        return 2
    return 1


# ---------------------------------------------------------------------------
# Reward function
# ---------------------------------------------------------------------------

def reward(state_idx: int, action_idx: int) -> float:
    """
    Immediate reward R(s, a).

    Design rationale
    ----------------
    fishing     : requires proximity to water (low water_dist is good).
    farming     : needs flat, smooth land (low slope + low roughness).
    residential : prefers flat land; penalises rough terrain and flood risk.
    forest      : tolerates steep / rough terrain unsuitable for other uses;
                  kept as a low-base-reward fallback.

    Weights are asymmetric — large penalties for clearly wrong placements,
    moderate rewards for correct ones — so the policy avoids catastrophic
    mismatches rather than merely preferring good ones.
    """
    slope_bin, roughness_bin, water_bin = decode_state(state_idx)
    action = ACTIONS[action_idx]
    r = 0.0

    if action == "fishing":
        if water_bin == 0:   r += 1.0    # close to water — ideal
        elif water_bin == 1: r += 0.2
        else:                r -= 1.0    # far from water — wrong biome

    elif action == "farming":
        if slope_bin == 0:       r += 1.0   # flat land — ideal
        elif slope_bin == 2:     r -= 0.8   # steep — crops won't grow
        if roughness_bin == 0:   r += 0.3
        elif roughness_bin == 2: r -= 0.3

    elif action == "residential":
        if slope_bin == 0:       r += 1.2   # flat — easy to build on
        elif slope_bin == 1:     r += 0.3   # gentle slope — acceptable
        elif slope_bin == 2:     r -= 0.7   # steep — bad for housing
        if roughness_bin == 0:   r += 0.2   # smooth bonus
        if roughness_bin == 2:   r -= 0.5   # rough — unstable
        if water_bin == 0:       r -= 0.6   # flood risk — strong penalty
        if water_bin == 2:       r += 0.3   # safely away from water

    elif action == "forest":
        r += 0.1                            # low base so it only wins when others lose
        if slope_bin == 2:       r += 0.5   # steep land → forest
        if roughness_bin == 2:   r += 0.4   # rough terrain → forest
        if slope_bin == 0 and roughness_bin == 0:
            r -= 0.4                        # waste of prime buildable space

    return r


# ---------------------------------------------------------------------------
# MDP solver
# ---------------------------------------------------------------------------

class DistrictMDP:
    """
    Tabular MDP for district type assignment solved via value iteration.

    The state space is fully enumerable (27 states) so value iteration
    converges in well under 200 iterations — typically fewer than 50.

    Parameters
    ----------
    gamma : float
        Discount factor. Because this MDP has no state transitions (each
        assignment is independent), gamma has no effect on the solution.
        Included for pedagogical correctness and future extensibility.
    """

    def __init__(self, gamma: float = 0.9) -> None:
        self.gamma = gamma
        self.Q:  np.ndarray = np.zeros((N_STATES, N_ACTIONS), dtype=float)
        self.V:  np.ndarray = np.zeros(N_STATES, dtype=float)
        self.pi: np.ndarray = np.zeros(N_STATES, dtype=int)
        self._solved = False

    # ------------------------------------------------------------------
    # Value iteration
    # ------------------------------------------------------------------

    def solve(self, iterations: int = 200, theta: float = 1e-6) -> None:
        """
        Run value iteration to compute the optimal Q-table and policy.

        Because there are no state transitions the Bellman backup reduces to:
            Q*(s, a) = R(s, a)
            V*(s)    = max_a Q*(s, a)
            pi*(s)   = argmax_a Q*(s, a)

        The iteration loop is kept so convergence is observable in logs and
        the code is easy to extend with transition dynamics later.

        Parameters
        ----------
        iterations : int
            Maximum number of sweeps.
        theta : float
            Convergence threshold on max |V_new − V_old|.
        """
        V = self.V.copy()

        for _ in range(iterations):
            delta = 0.0
            for s in range(N_STATES):
                q_vals = np.array([reward(s, a) for a in range(N_ACTIONS)])
                v_new  = float(np.max(q_vals))
                delta  = max(delta, abs(v_new - V[s]))
                V[s]   = v_new
            if delta < theta:
                break

        for s in range(N_STATES):
            for a in range(N_ACTIONS):
                self.Q[s, a] = reward(s, a)
            self.pi[s] = int(np.argmax(self.Q[s]))

        self.V       = V
        self._solved = True

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def act(
        self,
        slope:      float,
        roughness:  float,
        water_dist: float,
        slope_thresholds:     tuple[float, float] = (5.0, 20.0),
        roughness_thresholds: tuple[float, float] = (1.0,  3.0),
        water_thresholds:     tuple[float, float] = (8.0, 30.0),
    ) -> str:
        """
        Return the optimal district type for the given terrain metrics.

        Parameters
        ----------
        slope, roughness, water_dist : float
            Raw terrain values from WorldAnalysisResult.
        *_thresholds : tuple[float, float]
            (low, high) bin boundaries — values from thresholds_from_terrain()
            or thresholds_from_config(). Values below low → bin 0 (low),
            above high → bin 2 (high), between → bin 1 (mid).

        Returns
        -------
        str
            One of "fishing", "farming", "residential", "forest".
        """
        if not self._solved:
            self.solve()

        s_idx = state_index(
            discretise(slope,      *slope_thresholds),
            discretise(roughness,  *roughness_thresholds),
            discretise(water_dist, *water_thresholds),
        )
        return ACTIONS[self.pi[s_idx]]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def policy_table(self) -> str:
        """Return a human-readable policy table for all 27 states."""
        if not self._solved:
            self.solve()

        header = (
            f"{'slope':>6} {'rough':>6} {'water':>6}"
            f"  →  {'action':<12}  {'V*(s)':>7}"
        )
        lines  = [header, "─" * len(header)]
        labels = ["low", "mid", "high"]

        for s in range(N_STATES):
            sb, rb, wb = decode_state(s)
            lines.append(
                f"{labels[sb]:>6} {labels[rb]:>6} {labels[wb]:>6}"
                f"  →  {ACTIONS[self.pi[s]]:<12}  {self.V[s]:>7.3f}"
            )
        return "\n".join(lines)

    def q_table_summary(self) -> str:
        """Return Q-table as a readable string (debugging / report appendix)."""
        if not self._solved:
            self.solve()

        header = f"{'s':>3}  " + "  ".join(f"{a:>12}" for a in ACTIONS)
        lines  = [header, "─" * len(header)]

        for s in range(N_STATES):
            lines.append(
                f"{s:>3}  "
                + "  ".join(f"{self.Q[s, a]:>12.3f}" for a in range(N_ACTIONS))
            )
        return "\n".join(lines)