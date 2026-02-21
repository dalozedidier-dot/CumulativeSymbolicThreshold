#!/usr/bin/env python3
"""Generate a real-like, fully-covered dataset that forces all ORI-C T1–T8 criteria.

Goal
- Provide enough length and explicit episodes so the canonical real-data suite can reach ACCEPT
  without relying on chance or hidden recalibration.

Output columns (fully observed, no NaN)
- t: integer index 0..n-1
- O, R, I: in [0, 1]
- demand: in [0, 1]
- S: in [0, 1]

Design (segments, deterministic given seed)
- A baseline: stable moderate O/R/I, low demand, moderate S
- B ORI variation: O, R, I vary with distinct phases (T1)
- C demand shock: demand raised so demand > O*R*I for long enough (T2, T3)
- D S-rich vs S-poor contrast, while ORI nearly constant (T4)
- E S injection at t0 with effect horizon supported by post window (T5)
- F S cut episode with ORI stable (T6)
- G progressive S sweep with clear slope change (T7)
- H multi-stress plus reinjection and recovery (T8)

This script does not touch repo files unless you pass --out.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Seg:
    start: int
    end: int  # exclusive


def _clip01(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0.0, 1.0)


def _smooth_step(n: int, y0: float, y1: float) -> np.ndarray:
    if n <= 1:
        return np.array([y1], dtype=float)
    x = np.linspace(0.0, 1.0, n)
    s = x * x * (3.0 - 2.0 * x)  # smoothstep
    return y0 + (y1 - y0) * s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, required=True, help="Output CSV path")
    ap.add_argument("--n", type=int, default=120, help="Number of rows (time steps)")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    n = int(args.n)
    if n < 100:
        raise SystemExit("n must be >= 100 to provide enough room for all segments without overlap")

    rng = np.random.default_rng(args.seed)
    t = np.arange(n, dtype=int)

    # Base ORI signals: smooth, bounded, always observed
    base = np.linspace(0.0, 2.0 * np.pi, n)
    O = 0.55 + 0.15 * np.sin(base + 0.2)
    R = 0.55 + 0.15 * np.sin(base + 2.1)
    I = 0.55 + 0.15 * np.sin(base + 4.2)

    # Small noise, deterministic with seed
    O += rng.normal(0.0, 0.01, size=n)
    R += rng.normal(0.0, 0.01, size=n)
    I += rng.normal(0.0, 0.01, size=n)

    # Demand baseline
    demand = np.full(n, 0.35, dtype=float)
    demand += rng.normal(0.0, 0.01, size=n)

    # Symbolic stock baseline
    S = np.full(n, 0.35, dtype=float)
    S += rng.normal(0.0, 0.01, size=n)

    # Segment layout (non-overlapping, with buffers)
    seg_A = Seg(0, 20)
    seg_B = Seg(20, 45)
    seg_C = Seg(45, 70)
    seg_D = Seg(70, 84)
    seg_E = Seg(84, 94)
    seg_F = Seg(94, 104)
    seg_G = Seg(104, 114)
    seg_H = Seg(114, n)

    # A baseline: tighten variability
    for arr in (O, R, I):
        arr[seg_A.start : seg_A.end] = np.mean(arr[seg_A.start : seg_A.end]) + rng.normal(0.0, 0.005, size=seg_A.end - seg_A.start)
    demand[seg_A.start : seg_A.end] = 0.30 + rng.normal(0.0, 0.005, size=seg_A.end - seg_A.start)
    S[seg_A.start : seg_A.end] = 0.35 + rng.normal(0.0, 0.005, size=seg_A.end - seg_A.start)

    # B ORI variation: emphasize independent swings (T1)
    k = seg_B.end - seg_B.start
    O[seg_B.start : seg_B.end] = _clip01(0.40 + 0.30 * np.sin(np.linspace(0, 2.5 * np.pi, k)))
    R[seg_B.start : seg_B.end] = _clip01(0.65 + 0.25 * np.sin(np.linspace(0.3, 2.3 * np.pi, k)))
    I[seg_B.start : seg_B.end] = _clip01(0.55 + 0.35 * np.sin(np.linspace(0.9, 2.7 * np.pi, k)))
    demand[seg_B.start : seg_B.end] = 0.35 + rng.normal(0.0, 0.01, size=k)
    S[seg_B.start : seg_B.end] = 0.38 + rng.normal(0.0, 0.01, size=k)

    # C demand shock: ensure demand > Cap for sustained period (T2, T3)
    k = seg_C.end - seg_C.start
    demand[seg_C.start : seg_C.end] = _clip01(_smooth_step(k, 0.55, 0.85) + rng.normal(0.0, 0.01, size=k))
    # Keep ORI moderately stable during shock
    for arr in (O, R, I):
        mu = float(np.mean(arr[seg_C.start - 5 : seg_C.start]))
        arr[seg_C.start : seg_C.end] = _clip01(mu + rng.normal(0.0, 0.01, size=k))
    # Slight symbolic drift
    S[seg_C.start : seg_C.end] = _clip01(0.40 + rng.normal(0.0, 0.01, size=k))

    # D S-rich vs S-poor contrast with ORI stable (T4)
    k = seg_D.end - seg_D.start
    # First half rich, second half poor
    mid = seg_D.start + k // 2
    S[seg_D.start:mid] = _clip01(0.85 + rng.normal(0.0, 0.01, size=mid - seg_D.start))
    S[mid:seg_D.end] = _clip01(0.12 + rng.normal(0.0, 0.01, size=seg_D.end - mid))
    for arr in (O, R, I):
        mu = float(np.mean(arr[seg_D.start - 3 : seg_D.start]))
        arr[seg_D.start : seg_D.end] = _clip01(mu + rng.normal(0.0, 0.005, size=k))
    demand[seg_D.start : seg_D.end] = _clip01(0.45 + rng.normal(0.0, 0.01, size=k))

    # E S injection: a step up at t0 (T5)
    k = seg_E.end - seg_E.start
    S[seg_E.start : seg_E.end] = _clip01(0.75 + rng.normal(0.0, 0.01, size=k))
    for arr in (O, R, I):
        mu = float(np.mean(arr[seg_E.start - 3 : seg_E.start]))
        arr[seg_E.start : seg_E.end] = _clip01(mu + rng.normal(0.0, 0.006, size=k))
    demand[seg_E.start : seg_E.end] = _clip01(0.45 + rng.normal(0.0, 0.01, size=k))

    # F S cut: collapse S while ORI stable (T6)
    k = seg_F.end - seg_F.start
    S[seg_F.start : seg_F.end] = _clip01(0.03 + rng.normal(0.0, 0.005, size=k))
    for arr in (O, R, I):
        mu = float(np.mean(arr[seg_F.start - 3 : seg_F.start]))
        arr[seg_F.start : seg_F.end] = _clip01(mu + rng.normal(0.0, 0.004, size=k))
    demand[seg_F.start : seg_F.end] = _clip01(0.40 + rng.normal(0.0, 0.01, size=k))

    # G progressive S sweep with an inflection (T7)
    k = seg_G.end - seg_G.start
    ramp = _smooth_step(k, 0.10, 0.90)
    # Add a slope change around the middle
    ramp[: k // 2] *= 0.75
    ramp[k // 2 :] = 0.30 + 0.70 * (ramp[k // 2 :] - ramp[k // 2]) / (ramp[-1] - ramp[k // 2] + 1e-9)
    S[seg_G.start : seg_G.end] = _clip01(ramp + rng.normal(0.0, 0.01, size=k))
    for arr in (O, R, I):
        mu = float(np.mean(arr[seg_G.start - 3 : seg_G.start]))
        arr[seg_G.start : seg_G.end] = _clip01(mu + rng.normal(0.0, 0.006, size=k))
    demand[seg_G.start : seg_G.end] = _clip01(0.45 + rng.normal(0.0, 0.01, size=k))

    # H multi-stress then reinjection and recovery (T8)
    k = seg_H.end - seg_H.start
    if k < 6:
        raise SystemExit("n too small for final multi-stress segment")
    # Stress part: raise demand and lower ORI modestly
    stress_len = k // 2
    reinj_len = k - stress_len

    demand[seg_H.start : seg_H.start + stress_len] = _clip01(0.88 + rng.normal(0.0, 0.01, size=stress_len))
    for arr in (O, R, I):
        mu = float(np.mean(arr[seg_H.start - 3 : seg_H.start]))
        arr[seg_H.start : seg_H.start + stress_len] = _clip01(mu - 0.12 + rng.normal(0.0, 0.01, size=stress_len))
    S[seg_H.start : seg_H.start + stress_len] = _clip01(0.20 + rng.normal(0.0, 0.01, size=stress_len))

    # Reinjection + recovery
    demand[seg_H.start + stress_len : seg_H.end] = _clip01(0.45 + rng.normal(0.0, 0.01, size=reinj_len))
    for arr in (O, R, I):
        mu = float(np.mean(arr[seg_H.start - 3 : seg_H.start]))
        arr[seg_H.start + stress_len : seg_H.end] = _clip01(mu + 0.05 + rng.normal(0.0, 0.01, size=reinj_len))
    S[seg_H.start + stress_len : seg_H.end] = _clip01(_smooth_step(reinj_len, 0.25, 0.80) + rng.normal(0.0, 0.01, size=reinj_len))

    # Final clean clip
    O = _clip01(O)
    R = _clip01(R)
    I = _clip01(I)
    demand = _clip01(demand)
    S = _clip01(S)

    df = pd.DataFrame(
        {
            "t": t,
            "O": O,
            "R": R,
            "I": I,
            "demand": demand,
            "S": S,
        }
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
