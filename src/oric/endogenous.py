"""endogenous.py — An ORI-C model that *instantiates* the mechanism it postulates.

Why this module exists
----------------------
The canonical ORI-C simulator (``ori_c_pipeline``) has **no state-dependent
feedback**:

    S(t+1) = S(t) + α·Σ_sym − δ·S(t)        (leaky integrator of an exogenous Σ)
    C(t+1) = C(t) + β·S(t) − γ·V(t)         (cumulative sum of a driven S)

There is no S→S autocatalysis and no C→S / C→{O,R,I} coupling, so the system has
a single, globally attracting trajectory: no multiplicity of fixed points, no
saddle-node, no pitchfork. It therefore *cannot* generate endogenously the
"self-reinforcing cumulative symbolic regime" the framework claims; any apparent
"bifurcation" is a steep curve imposed on the input ``demand`` channel, and the
localized detector merely discriminates "steep step" from "smooth ramp" on the
*input* (see ``accumulation_controls`` and ``docs/EVIDENTIARY_STATUS.md`` §3a).

This module supplies the missing ingredient: a genuine **endogenous positive
feedback** so the symbolic channel can self-amplify. The order parameter ``C``
obeys a recovering/folding dynamic of the canonical critical-transition form
(May 1977; Scheffer et al. 2009, *Nature* 461:53):

    dC/dt = a(t) − b·C + r·C^p / (C^p + h^p) + √(2D)·ξ(t)

where the Hill term ``r·C^p/(C^p+h^p)`` is the self-reinforcement (the gain rises
with ``C`` and saturates), ``b·C`` is the linear leak, and ``a(t)`` is the
**control parameter** — the slowly varying symbolic load, grounded in ORI-C as
``a = a0 + g·S`` with ``S`` the usual leaky integrator of the O·R·I→Cap→Σ
mismatch. For a window of ``a`` the deterministic field has two stable fixed
points (a low and a high branch) separated by an unstable one: the system is
**bistable**. Sweeping ``a`` up, the low branch annihilates at a fold and the
state jumps to the high branch; sweeping back down, it stays high until a lower
fold — i.e. **hysteresis**. Near either fold the recovery rate |f'(C*)|→0, so the
state shows **critical slowing down** (rising lag-1 autocorrelation and variance)
*before* the jump — signatures a smooth trend cannot fake (see ``early_warning``).

Contrast control (the matched non-bifurcating twin)
---------------------------------------------------
Setting ``r = 0`` removes the feedback: dC/dt = a − b·C, a monostable linear
relaxation that tracks ``a/b``. Driven by the *same* ``a(t)`` and the *same*
noise, the twin produces a smooth ramp with **no fold, no hysteresis, no
critical slowing down**. This is the decisive negative control: any statistic
that fires on the bistable model but not on its linear twin isolates the
*endogenous transition*, not the drive.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EndogenousConfig:
    """Parameters of the endogenous bistable ORI-C model.

    Defaults are chosen so the deterministic field is bistable over a clear
    window of the control parameter ``a`` (verified in tests via
    :func:`bistable_window`). ``b``, ``r``, ``h`` shape the fold; ``hill_p``
    controls the steepness of the self-reinforcement.
    """

    # Bistable order-parameter dynamics  dC/dt = a − b·C + r·C^p/(C^p+h^p)
    b: float = 1.0           # linear leak
    r: float = 2.6           # self-reinforcement strength (feedback gain)
    h: float = 1.0           # half-saturation of the Hill feedback
    hill_p: float = 4.0      # Hill exponent (steepness of self-reinforcement)

    # Noise (additive, in C units) — required for critical-slowing-down signatures
    noise_sd: float = 0.02

    # Integration
    dt: float = 0.05         # internal Euler step
    substeps: int = 4        # internal substeps per output step
    C0: float = 0.0          # initial order parameter (on the low branch)

    # ORI-C grounding: control parameter a = a0 + g·S, S leaky integrator of Σ_sym
    a0: float = 0.0
    g: float = 1.0
    sigma_to_S: float = 1.0
    S_decay: float = 0.02
    sigma_star: float = 0.0
    S0: float = 0.0

    seed: int = 1234

    def linear_twin(self) -> "EndogenousConfig":
        """Return the matched non-bifurcating twin (feedback off, r = 0)."""
        return replace(self, r=0.0)


# ---------------------------------------------------------------------------
# Deterministic field, fixed points, and the bistable window
# ---------------------------------------------------------------------------

def _hill(C: np.ndarray | float, r: float, h: float, p: float) -> np.ndarray | float:
    """Self-reinforcement term r·C^p/(C^p + h^p) (0 for C ≤ 0)."""
    Cp = np.power(np.clip(C, 0.0, None), p)
    return np.asarray(r * Cp / (Cp + h**p), dtype=float)


def field(C: np.ndarray | float, a: float, cfg: EndogenousConfig) -> np.ndarray | float:
    """The deterministic vector field f(C; a) = a − b·C + r·C^p/(C^p+h^p)."""
    return a - cfg.b * np.asarray(C, dtype=float) + _hill(C, cfg.r, cfg.h, cfg.hill_p)


def equilibria(a: float, cfg: EndogenousConfig, *, c_max: float | None = None,
               grid: int = 4000) -> list[tuple[float, bool]]:
    """Return [(C*, is_stable), ...] fixed points of the field for control ``a``.

    Roots are found by sign changes of f on a fine grid then bisection; a root is
    stable iff f decreases through zero (f'(C*) < 0).
    """
    if c_max is None:
        # Upper bound: above the high branch a − b·C + r is negative, so C* < (a+r)/b.
        c_max = max(2.0 * cfg.h, (a + cfg.r) / cfg.b + 2.0 * cfg.h)
    C = np.linspace(0.0, float(c_max), int(grid))
    f = np.asarray(field(C, a, cfg), dtype=float)
    # Candidate brackets: any interval whose endpoints straddle (or touch) zero.
    # Exact-zero grid points yield two adjacent brackets; they are de-duplicated
    # below so a root landing on the grid is not counted twice.
    idx = np.where(f[:-1] * f[1:] <= 0.0)[0]
    raw: list[float] = []
    for i in idx:
        lo, hi = float(C[i]), float(C[i + 1])
        flo, fhi = float(f[i]), float(f[i + 1])
        if flo == 0.0:
            raw.append(lo)
            continue
        if fhi == 0.0:
            raw.append(hi)
            continue
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            fmid = float(field(mid, a, cfg))
            if flo * fmid <= 0.0:
                hi = mid
            else:
                lo, flo = mid, fmid
        raw.append(0.5 * (lo + hi))
    raw.sort()
    roots: list[tuple[float, bool]] = []
    last = None
    for Cstar in raw:
        if last is not None and abs(Cstar - last) <= 1e-6 * max(1.0, abs(Cstar)) + 1e-9:
            continue
        last = Cstar
        eps = 1e-4 * max(1.0, Cstar)
        slope = float(field(Cstar + eps, a, cfg) - field(Cstar - eps, a, cfg)) / (2 * eps)
        roots.append((float(Cstar), bool(slope < 0.0)))
    return roots


def bistable_window(cfg: EndogenousConfig, *, a_min: float = -2.0, a_max: float = 4.0,
                    n: int = 600) -> tuple[float, float] | None:
    """Return (a_low, a_high): the range of ``a`` with two stable fixed points.

    Returns ``None`` if the configuration is not bistable anywhere on the grid.
    """
    a_grid = np.linspace(a_min, a_max, int(n))
    bistable_as = [a for a in a_grid if sum(s for _, s in equilibria(float(a), cfg)) >= 2]
    if not bistable_as:
        return None
    return float(min(bistable_as)), float(max(bistable_as))


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate(a_traj: np.ndarray, cfg: EndogenousConfig,
             rng: np.random.Generator | None = None) -> np.ndarray:
    """Integrate the order parameter ``C`` under a control-parameter trajectory.

    ``a_traj`` is the per-output-step control parameter ``a(t)``. Integration uses
    ``cfg.substeps`` Euler–Maruyama substeps of size ``cfg.dt`` per output step.
    Returns the array of ``C`` at each output step.
    """
    rng = np.random.default_rng(cfg.seed) if rng is None else rng
    a_traj = np.asarray(a_traj, dtype=float)
    n = a_traj.size
    C = float(cfg.C0)
    out = np.empty(n, dtype=float)
    sd_step = cfg.noise_sd * np.sqrt(cfg.dt)
    for t in range(n):
        a = float(a_traj[t])
        for _ in range(int(cfg.substeps)):
            C += float(field(C, a, cfg)) * cfg.dt + sd_step * float(rng.standard_normal())
            if C < 0.0:
                C = 0.0
        out[t] = C
    return out


def run_endogenous(a_traj: np.ndarray, cfg: EndogenousConfig,
                   rng: np.random.Generator | None = None) -> pd.DataFrame:
    """Simulate and return a DataFrame (t, a, C, delta_C) for one control trajectory."""
    C = simulate(a_traj, cfg, rng=rng)
    df = pd.DataFrame({"t": np.arange(C.size), "a": np.asarray(a_traj, dtype=float), "C": C})
    df["delta_C"] = df["C"].diff().fillna(0.0)
    return df


# ---------------------------------------------------------------------------
# ORI-C grounding: drive the control parameter from a Σ-mismatch series
# ---------------------------------------------------------------------------

def drive_from_sigma(sigma_sym: np.ndarray, cfg: EndogenousConfig) -> np.ndarray:
    """Map a symbolic-mismatch series Σ_sym(t) to the control parameter a(t).

    ``S`` is the usual leaky integrator S(t+1)=S(t)+ι·Σ_sym−δ_S·S, and the control
    parameter is a = a0 + g·S. This preserves the ORI-C chain
    O·R·I→Cap→Σ→S while making ``C`` the endogenously bistable order variable.
    """
    sigma_sym = np.asarray(sigma_sym, dtype=float)
    n = sigma_sym.size
    S = float(cfg.S0)
    a = np.empty(n, dtype=float)
    for t in range(n):
        S = S + cfg.sigma_to_S * max(0.0, float(sigma_sym[t]) - cfg.sigma_star) - cfg.S_decay * S
        a[t] = cfg.a0 + cfg.g * S
    return a


# ---------------------------------------------------------------------------
# Control-parameter trajectories
# ---------------------------------------------------------------------------

def make_ramp(n: int, a_start: float, a_end: float, *, hold_frac: float = 0.0) -> np.ndarray:
    """A monotone ramp from ``a_start`` to ``a_end`` (optionally holding the ends)."""
    n = int(n)
    hold = int(round(hold_frac * n))
    body = n - 2 * hold
    body = max(1, body)
    mid = np.linspace(a_start, a_end, body)
    return np.concatenate([np.full(hold, a_start), mid, np.full(n - hold - body, a_end)])


def _fold_setup(cfg: EndogenousConfig, n: int, cross: bool,
                a_start: float | None, a_end: float | None) -> tuple[np.ndarray, float]:
    """Return (a_traj, C0) for a low-branch run-up toward (or across) the upper fold."""
    win = bistable_window(cfg)
    if win is None:
        raise ValueError("configuration is not bistable; cannot build a fold approach")
    a_low, a_high = win
    if a_start is None:
        a_start = a_low + 0.15 * (a_high - a_low)
    if a_end is None:
        a_end = a_high * 1.08 if cross else a_low + 0.92 * (a_high - a_low)
    stable = [c for c, s in equilibria(float(a_start), cfg) if s]
    C0 = min(stable) if stable else 0.0
    return make_ramp(int(n), float(a_start), float(a_end)), float(C0)


def fold_approach(cfg: EndogenousConfig, *, n: int = 600, cross: bool = False,
                  a_start: float | None = None, a_end: float | None = None,
                  rng: np.random.Generator | None = None) -> pd.DataFrame:
    """Generate a low-branch run-up toward the fold (the canonical transition setup).

    The system starts on its **low** stable branch and the control parameter ``a``
    is ramped up. With ``cross=False`` it approaches the upper fold without crossing
    (pure pre-transition run-up, for CSD); with ``cross=True`` it crosses the fold
    and jumps to the high branch. Returns a DataFrame (t, a, C, delta_C).
    """
    a_traj, C0 = _fold_setup(cfg, n, cross, a_start, a_end)
    return run_endogenous(a_traj, replace(cfg, C0=C0), rng=rng)


def matched_fold_pair(cfg: EndogenousConfig, *, n: int = 600, cross: bool = False,
                      a_start: float | None = None, a_end: float | None = None,
                      seed: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (bistable, linear-twin) runs on the **same** drive, start, and noise.

    The matched twin (feedback off) is the decisive negative control: identical
    control trajectory ``a(t)``, identical initial ``C0`` (the bistable low branch),
    and identical noise stream — so any difference is the endogenous feedback alone.
    """
    a_traj, C0 = _fold_setup(cfg, n, cross, a_start, a_end)
    cfg_b = replace(cfg, C0=C0)
    df_b = run_endogenous(a_traj, cfg_b, rng=np.random.default_rng(seed))
    df_t = run_endogenous(a_traj, cfg_b.linear_twin(), rng=np.random.default_rng(seed))
    return df_b, df_t


def hysteresis_sweep(cfg: EndogenousConfig, *, a_min: float, a_max: float,
                     n_up: int = 400, n_down: int = 400,
                     rng: np.random.Generator | None = None) -> dict:
    """Sweep ``a`` up then back down and quantify the hysteresis loop.

    Returns a dict with the up/down branches and ``hysteresis_area`` — the signed
    area between the up and down C(a) curves. A genuine fold gives a non-zero
    loop; the linear twin gives ≈ 0.
    """
    rng = np.random.default_rng(cfg.seed) if rng is None else rng
    up = make_ramp(n_up, a_min, a_max)
    down = make_ramp(n_down, a_max, a_min)
    a_full = np.concatenate([up, down])
    C = simulate(a_full, cfg, rng=rng)
    C_up, C_down = C[:n_up], C[n_up:]
    # Interpolate both branches on a common a-grid and integrate the gap.
    a_grid = np.linspace(a_min, a_max, 200)
    up_interp = np.interp(a_grid, up, C_up)
    down_interp = np.interp(a_grid, down[::-1], C_down[::-1])
    # numpy >= 2 renamed trapz -> trapezoid; getattr keeps both paths type-clean.
    trapz_fn = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    area = float(trapz_fn(np.abs(down_interp - up_interp), a_grid))
    return {
        "a_grid": a_grid, "C_up": up_interp, "C_down": down_interp,
        "hysteresis_area": area, "a_min": float(a_min), "a_max": float(a_max),
    }
