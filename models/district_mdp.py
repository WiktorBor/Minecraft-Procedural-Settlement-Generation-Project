"""
district_mdp.py
---------------
MDP-based district type assignment via value iteration.

Replaces the rule-based _assign_type heuristic in DistrictPlanner with a
policy learned offline through value iteration on a small, fully enumerable
state space (27 states × 4 actions).

Usage
-----
In DistrictPlanner.__init__, add:

    from ai.district_mdp import DistrictMDP, thresholds_from_config
    self._mdp = DistrictMDP(gamma=0.9)
    self._mdp.solve(iterations=200)
    self._thresholds = thresholds_from_config(config)

Then replace the body of _assign_type with:

    return self._mdp.act(slope, roughness, water_dist, **self._thresholds)

The MDP is solved once at construction time — O(27 × 4 × iterations) work,
negligible compared to the Voronoi computation.

Threshold derivation
--------------------
Bin boundaries are derived from SettlementConfig via thresholds_from_config():

  slope     : low = farming slope_max (3.0),  high = SettlementConfig.max_slope * 3
  roughness : low = farming roughness_max / 2, high = SettlementConfig.max_roughness
  water     : low = fishing water_dist_max (10), high = water_dist_max * 3

This means the bins are anchored to the same numbers that govern the rest of
your settlement logic — a single source of truth, easy to justify in a report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    # Avoids a circular import at runtime; only used for type hints.
    from data.configurations import SettlementConfig


# ---------------------------------------------------------------------------
# Config → threshold helper
# ---------------------------------------------------------------------------

def thresholds_from_config(config: "SettlementConfig") -> dict:
    """
    Derive MDP bin thresholds directly from SettlementConfig values.

    This keeps the MDP anchored to the same numbers that govern the rest of
    the settlement logic — one source of truth, easy to justify in a report.

    Bin logic (same for all three features):
        value <= low_thresh  → bin 0  (low / favourable)
        low_thresh < value < high_thresh → bin 1 (mid)
        value >= high_thresh → bin 2  (high / unfavourable)

    Derivation
    ----------
    slope
        low  = farming slope_max   (terrain flat enough for crops)
        high = SettlementConfig.max_slope * 3  (well above the plot placement limit)

    roughness
        low  = farming roughness_max / 2  (smooth enough for crops)
        high = SettlementConfig.max_roughness  (at the plot placement hard limit)

    water distance
        low  = fishing water_dist_max  (close enough for a fishing village)
        high = fishing water_dist_max * 3  (far enough to rule out fishing entirely)
    """
    farming_rules = config.district_type_rules.get("farming", {})
    fishing_rules = config.district_type_rules.get("fishing", {})

    slope_low   = float(farming_rules.get("slope_max",     3.0))
    slope_high  = float(config.max_slope) * 3

    rough_low   = float(farming_rules.get("roughness_max", 8.0)) / 2
    rough_high  = float(config.max_roughness)

    water_low   = float(fishing_rules.get("water_dist_max", 10.0))
    water_high  = water_low * 3

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

# Number of bins for each terrain feature.
# 0 = low, 1 = medium, 2 = high
N_BINS = 3

# Total number of states = N_BINS ^ 3 = 27
N_STATES = N_BINS ** 3
N_ACTIONS = len(ACTIONS)


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

    Parameters
    ----------
    value        : the raw terrain metric
    low_thresh   : anything below this → bin 0 (low)
    high_thresh  : anything above this → bin 2 (high)
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

    Design rationale (for the report):
    -----------------------------------
    Each rule encodes a domain principle about how terrain features relate
    to appropriate district types:

    fishing     : requires proximity to water (low water_dist = good).
    farming     : needs flat, smooth land (low slope + low roughness).
    residential : prefers flat land, penalises rough terrain and flood risk
                  (very low water_dist raises flood concern).
    forest      : tolerates steep and rough terrain that is unsuitable for
                  other uses; acts as a well-rewarded fallback.

    Weights are intentionally asymmetric — large penalties for clearly wrong
    placements, moderate rewards for correct ones — so the learned policy
    avoids catastrophic mismatches rather than merely preferring good ones.

    To tune: adjust the float values below; re-run DistrictMDP.solve().
    The reward table is small enough to inspect in full, making it easy to
    verify in a report that the policy is behaving as intended.
    """
    slope_bin, roughness_bin, water_bin = decode_state(state_idx)
    action = ACTIONS[action_idx]
    r = 0.0

    if action == "fishing":
        if water_bin == 0:   r += 1.0   # close to water — ideal
        elif water_bin == 1: r += 0.2
        else:                r -= 1.0   # far from water — wrong biome

    elif action == "farming":
        if slope_bin == 0:   r += 1.0   # flat land — ideal
        elif slope_bin == 2: r -= 0.8   # steep — crops won't grow
        if roughness_bin == 0: r += 0.3
        elif roughness_bin == 2: r -= 0.3

    elif action == "residential":
        # Residential wins on flat, smooth land away from water.
        # Raised above farming (1.0) so it appears when water_bin > 0.
        if slope_bin == 0:     r += 1.2  # flat — easy to build on
        elif slope_bin == 1:   r += 0.3  # gentle slope — acceptable
        elif slope_bin == 2:   r -= 0.7  # steep — bad for housing
        if roughness_bin == 0: r += 0.2  # smooth bonus
        if roughness_bin == 2: r -= 0.5  # rough terrain — unstable
        if water_bin == 0:     r -= 0.6  # flood risk — strong penalty
        if water_bin == 2:     r += 0.3  # safely away from water

    elif action == "forest":
        # Forest is the fallback for land unsuitable for anything else.
        # Base reward kept low so it only wins when others are penalised.
        r += 0.1
        if slope_bin == 2:     r += 0.5  # steep land → forest
        if roughness_bin == 2: r += 0.4  # rough terrain → forest
        # Penalise forest on prime flat land — waste of buildable space
        if slope_bin == 0 and roughness_bin == 0: r -= 0.4

    return r


# ---------------------------------------------------------------------------
# MDP solver
# ---------------------------------------------------------------------------

class DistrictMDP:
    """
    Stateless MDP for district type assignment, solved via value iteration.

    The state space is fully enumerable (27 states) so tabular value
    iteration converges in well under 200 iterations — typically < 50.

    Parameters
    ----------
    gamma      : discount factor (0 < gamma < 1).
                 For a single-step, stateless assignment problem there are
                 no successor states, so gamma has no effect here — included
                 for pedagogical correctness and future extensibility.
    """

    def __init__(self, gamma: float = 0.9) -> None:
        self.gamma = gamma

        # Q[s, a] — state-action value table, shape (27, 4)
        self.Q: np.ndarray = np.zeros((N_STATES, N_ACTIONS), dtype=float)

        # V[s] — state value, shape (27,)
        self.V: np.ndarray = np.zeros(N_STATES, dtype=float)

        # pi[s] — greedy policy, shape (27,) → action index
        self.pi: np.ndarray = np.zeros(N_STATES, dtype=int)

        self._solved = False

    # ------------------------------------------------------------------
    # Value iteration
    # ------------------------------------------------------------------

    def solve(self, iterations: int = 200, theta: float = 1e-6) -> None:
        """
        Run value iteration to compute the optimal Q-table and policy.

        Because this MDP has no state transitions (each district assignment
        is independent — terrain features don't change as a result of the
        action), the Bellman optimality equation reduces to:

            Q*(s, a) = R(s, a)
            V*(s)    = max_a Q*(s, a)
            pi*(s)   = argmax_a Q*(s, a)

        The iteration loop is retained for report correctness — it shows the
        algorithm converging (delta → 0 after a single pass in this case) —
        and makes the code easy to extend if transition dynamics are added
        later (e.g. modelling how neighbouring districts influence each other).

        Parameters
        ----------
        iterations : maximum number of sweeps
        theta      : convergence threshold on max |V_new - V_old|
        """
        V = self.V.copy()

        for _ in range(iterations):
            delta = 0.0
            for s in range(N_STATES):
                # Bellman optimality backup
                q_vals = np.array([reward(s, a) for a in range(N_ACTIONS)])
                # No successor states → future term = 0; kept for extensibility:
                # q_vals += self.gamma * transition[s, a, :] @ V  (if transitions exist)
                v_new = float(np.max(q_vals))
                delta = max(delta, abs(v_new - V[s]))
                V[s] = v_new

            if delta < theta:
                break

        # Final Q-table and greedy policy
        for s in range(N_STATES):
            for a in range(N_ACTIONS):
                self.Q[s, a] = reward(s, a)
            self.pi[s] = int(np.argmax(self.Q[s]))

        self.V = V
        self._solved = True

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def act(
        self,
        slope: float,
        roughness: float,
        water_dist: float,
        slope_thresholds:     tuple[float, float] = (5.0, 20.0),
        roughness_thresholds: tuple[float, float] = (1.0,  3.0),
        water_thresholds:     tuple[float, float] = (8.0, 30.0),
    ) -> str:
        """
        Return the optimal district type for a given set of terrain metrics.

        Parameters
        ----------
        slope, roughness, water_dist : raw terrain values from the analysis
        *_thresholds : (low, high) bin boundaries for each feature.
                       Tune these to match the typical range in your world.
                       Values below `low`  → bin 0 (low).
                       Values above `high` → bin 2 (high).
                       Values in between   → bin 1 (medium).

        Returns
        -------
        str : one of "fishing", "farming", "residential", "forest"
        """
        if not self._solved:
            self.solve()

        s_bin = discretise(slope,     *slope_thresholds)
        r_bin = discretise(roughness, *roughness_thresholds)
        w_bin = discretise(water_dist, *water_thresholds)

        s_idx = state_index(s_bin, r_bin, w_bin)
        return ACTIONS[self.pi[s_idx]]

    # ------------------------------------------------------------------
    # Introspection helpers (useful for the report)
    # ------------------------------------------------------------------

    def policy_table(self) -> str:
        """
        Return a human-readable policy table for all 27 states.
        Paste this into your report to show the learned policy.
        """
        if not self._solved:
            self.solve()

        header = f"{'slope':>6} {'rough':>6} {'water':>6}  →  {'action':<12}  {'V*(s)':>7}"
        lines  = [header, "-" * len(header)]
        labels = ["low", "mid", "high"]
        for s in range(N_STATES):
            sb, rb, wb = decode_state(s)
            action = ACTIONS[self.pi[s]]
            lines.append(
                f"{labels[sb]:>6} {labels[rb]:>6} {labels[wb]:>6}  →  {action:<12}  {self.V[s]:>7.3f}"
            )
        return "\n".join(lines)

    def q_table_summary(self) -> str:
        """Return Q-table as a readable string for debugging / report appendix."""
        if not self._solved:
            self.solve()

        header = f"{'s':>3}  " + "  ".join(f"{a:>12}" for a in ACTIONS)
        lines  = [header, "-" * len(header)]
        for s in range(N_STATES):
            sb, rb, wb = decode_state(s)
            row = f"{s:>3}  " + "  ".join(f"{self.Q[s, a]:>12.3f}" for a in range(N_ACTIONS))
            lines.append(row)
        return "\n".join(lines)