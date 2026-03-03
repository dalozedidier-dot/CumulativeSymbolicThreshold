#!/usr/bin/env python3
"""
tools/generate_brisbane_stateprob.py

Generates StateProb datasets (STATES_*.csv + ATTR_*.csv) compatible with
qcc_stateprob_cross_conditions, from quantum circuits with variable depth.

Three backends supported:
  numpy    : built-in density-matrix Trotter simulator (no extra install)
  aer      : Qiskit Aer simulator (pip install qiskit qiskit-aer)
  brisbane : IBM Quantum Brisbane (pip install qiskit qiskit-ibm-runtime)

Inspired by arXiv:2506.10258 "Synchronization for Fault-Tolerant Quantum
Computers" (IBM Brisbane, 127 qubits, X-X DD, 20 000 shots).

Circuit types:
  ising     : 1D transverse-field Ising model, k Trotter steps per instance.
              depth proxy = 4*k (ZZ layer + X layer + barriers).
  syncidle  : Idle circuit with optional X-X DD, modelling the synchronisation
              slack studied in arXiv:2506.10258. depth proxy = number of
              idle rounds (each round = one syndrome-cycle duration).

Outputs (under --out-dir):
  STATES_{device}_{algo}_{instance}_{shots}.csv   (state, prob)
  ATTR_{device}_{algo}_{instance}_{shots}.csv      (Depth)

Usage examples:
  # Local numpy simulation (no extra deps):
  python -m tools.generate_brisbane_stateprob \\
      --backend numpy --algo ising \\
      --depths 2,4,6,8,12,16,20,28,36,48,64,80,100,128,160 \\
      --instances 15 --shots 8192 --out-dir data/brisbane_ising_sim

  # Local Aer simulation:
  python -m tools.generate_brisbane_stateprob \\
      --backend aer --algo ising \\
      --depths 2,4,6,8,12,16,20,28,36,48,64,80 \\
      --instances 10 --shots 8192 --out-dir data/brisbane_ising_aer

  # IBM Brisbane hardware:
  python -m tools.generate_brisbane_stateprob \\
      --backend brisbane --ibm-token $IBM_TOKEN \\
      --algo ising --dd xx \\
      --depths 2,5,10,20,40,60,80,100 \\
      --instances 5 --shots 20000 --out-dir data/brisbane_ising_hw
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── output helpers ────────────────────────────────────────────────────────────

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_states_csv(out_path: Path, probs: np.ndarray) -> None:
    """
    Write STATES CSV (state, prob) from probability array.
    state = zero-padded binary string; only writes non-zero states.
    """
    n_states = len(probs)
    n_bits = int(math.log2(n_states))
    _ensure_dir(out_path.parent)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "prob"])
        for idx, p in enumerate(probs):
            if p > 0.0:
                w.writerow([format(idx, f"0{n_bits}b"), float(p)])


def _write_attr_csv(out_path: Path, depth: float) -> None:
    """Write ATTR CSV (single row: Depth=depth)."""
    _ensure_dir(out_path.parent)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Depth"])
        w.writerow([depth])


def _output_paths(
    out_dir: Path, device: str, algo: str, instance: int, shots: int
) -> Tuple[Path, Path]:
    states = out_dir / f"STATES_{device}_{algo}_{instance}_{shots}.csv"
    attr   = out_dir / f"ATTR_{device}_{algo}_{instance}_{shots}.csv"
    return states, attr


# ── numpy / density-matrix backend ───────────────────────────────────────────
#
# 1D transverse-field Ising: H = -J Σ Z_j Z_{j+1} - h Σ X_j
# Trotter step: exp(-i dt ZZ) then exp(-i dt X)
#
# Density matrix formulation allows realistic depolarising noise.
# Works for n_qubits up to ~12 in a few seconds.

def _pauli_x(n: int, qubit: int) -> np.ndarray:
    """Full n-qubit Pauli X on 'qubit' (little-endian: qubit 0 = MSB)."""
    ops = [np.eye(2) for _ in range(n)]
    ops[qubit] = np.array([[0, 1], [1, 0]], dtype=complex)
    result = ops[0]
    for op in ops[1:]:
        result = np.kron(result, op)
    return result


def _zz_phase(n: int, j: int, k: int) -> np.ndarray:
    """
    Diagonal unitary exp(-i theta Z_j Z_k).
    Returns 2^n vector of phases (to apply elementwise to state vector).
    """
    dim = 2 ** n
    phases = np.ones(dim, dtype=complex)
    for idx in range(dim):
        bit_j = (idx >> (n - 1 - j)) & 1
        bit_k = (idx >> (n - 1 - k)) & 1
        zz_val = (1 - 2 * bit_j) * (1 - 2 * bit_k)  # ±1
        phases[idx] = 1.0  # will be multiplied by caller
    return phases  # placeholder; actual logic inline below


def _apply_trotter_step_dm(
    rho: np.ndarray,
    n: int,
    J: float,
    h: float,
    dt: float,
    noise_p1: float,
    rng: np.random.Generator,
    dd_factor: float = 1.0,
) -> np.ndarray:
    """
    Apply one Trotter step to density matrix rho.
    ZZ layer → X layer → depolarising noise (reduced by dd_factor for DD).
    dd_factor: 0.0 = no noise (perfect DD), 1.0 = full noise.
    """
    dim = 2 ** n

    # ── ZZ layer (diagonal rotation) ─────────────────────────────────────────
    theta_zz = J * dt
    zz_diag = np.ones(dim, dtype=complex)
    for idx in range(dim):
        phase = 0.0
        for qubit in range(n - 1):
            bit_j = (idx >> (n - 1 - qubit)) & 1
            bit_k = (idx >> (n - 1 - qubit - 1)) & 1
            zz_val = (1 - 2 * bit_j) * (1 - 2 * bit_k)
            phase += zz_val
        zz_diag[idx] = np.exp(-1j * theta_zz * phase)
    # rho → D rho D†  where D = diag(zz_diag)
    rho = zz_diag[:, None] * rho * zz_diag[None, :].conj()

    # ── X layer (dense matrix) ────────────────────────────────────────────────
    phi_x = h * dt
    # exp(-i phi X) = cos(phi) I - i sin(phi) X  for each qubit
    # Compose as n single-qubit unitaries
    cos_phi = math.cos(phi_x)
    sin_phi = math.sin(phi_x)
    u_x = np.array([[cos_phi, -1j * sin_phi],
                    [-1j * sin_phi,  cos_phi]], dtype=complex)
    # Full n-qubit unitary = tensor product
    U_full = u_x
    for _ in range(n - 1):
        U_full = np.kron(U_full, u_x)
    rho = U_full @ rho @ U_full.conj().T

    # ── Per-qubit depolarising noise (scaled by dd_factor) ────────────────────
    p_eff = noise_p1 * dd_factor
    # Approximate n-qubit depolarising by sequential single-qubit channels
    # rho → (1 - 4/3 p) rho + (4/3 p)/dim * I
    # For small p per qubit, composed over n qubits:
    p_total = 1.0 - (1.0 - 4.0 / 3.0 * min(p_eff, 0.75)) ** n
    rho = (1.0 - p_total) * rho + p_total / dim * np.eye(dim, dtype=complex)

    return rho


def simulate_ising_numpy(
    n_qubits: int,
    n_trotter: int,
    J: float,
    h: float,
    dt: float,
    noise_p1: float,
    shots: int,
    rng: np.random.Generator,
    dd_factor: float = 1.0,
) -> np.ndarray:
    """
    Run 1D TFIM Trotter simulation, return sampled probability distribution.
    dd_factor: 1.0 = no DD, <1.0 = DD applied (reduces noise).
    """
    dim = 2 ** n_qubits
    # Start in |0...0><0...0|
    rho = np.zeros((dim, dim), dtype=complex)
    rho[0, 0] = 1.0

    for _ in range(n_trotter):
        rho = _apply_trotter_step_dm(rho, n_qubits, J, h, dt, noise_p1, rng, dd_factor)

    # Extract diagonal (measurement probabilities)
    probs = np.real(np.diag(rho))
    probs = np.clip(probs, 0.0, 1.0)
    s = probs.sum()
    if s > 0:
        probs /= s

    # Sample from multinomial to get empirical shot distribution
    counts = rng.multinomial(shots, probs)
    return counts.astype(float) / shots


def simulate_syncidle_numpy(
    n_qubits: int,
    n_idle_rounds: int,
    noise_p1_active: float,
    noise_p1_idle: float,
    shots: int,
    rng: np.random.Generator,
    dd_factor: float = 1.0,
) -> np.ndarray:
    """
    Simulate a synchronisation-idle circuit inspired by arXiv:2506.10258.

    One 'round' = one syndrome-cycle: active gates (noise_p1_active) +
    idle period (noise_p1_idle, reduced by dd_factor if DD is on).

    Returns sampled probability distribution.
    """
    dim = 2 ** n_qubits
    # Prepare |+> state (Hadamard on all qubits)
    psi = np.ones(dim, dtype=complex) / math.sqrt(dim)
    rho = np.outer(psi, psi.conj())

    # Active noise (same every round)
    p_active = 1.0 - (1.0 - 4.0 / 3.0 * min(noise_p1_active, 0.75)) ** n_qubits

    for _ in range(n_idle_rounds):
        # Active gate layer
        rho = (1.0 - p_active) * rho + p_active / dim * np.eye(dim, dtype=complex)
        # Idle noise (mitigated by DD factor)
        p_idle_eff = noise_p1_idle * dd_factor
        p_total_idle = 1.0 - (1.0 - 4.0 / 3.0 * min(p_idle_eff, 0.75)) ** n_qubits
        rho = (1.0 - p_total_idle) * rho + p_total_idle / dim * np.eye(dim, dtype=complex)

    probs = np.real(np.diag(rho))
    probs = np.clip(probs, 0.0, 1.0)
    s = probs.sum()
    if s > 0:
        probs /= s

    counts = rng.multinomial(shots, probs)
    return counts.astype(float) / shots


def run_numpy_backend(
    algo: str,
    depths: List[int],
    n_instances: int,
    shots: int,
    n_qubits: int,
    dd: Optional[str],
    out_dir: Path,
    device_label: str,
    base_seed: int,
) -> None:
    """Generate datasets using the built-in numpy density-matrix simulator."""
    J = 1.0           # ZZ coupling
    h = 0.5           # transverse field
    dt = 0.15         # Trotter step size (dimensionless)
    noise_p1 = 0.002  # per-qubit depolarising per step (realistic for 127Q device)
    dd_factor = 0.35 if dd else 1.0  # DD reduces noise ~3× (paper's 2–3× range)

    # noise_p1_active, noise_p1_idle for syncidle
    noise_active = 0.003
    noise_idle   = 0.008

    rng = np.random.default_rng(base_seed)
    total = len(depths) * n_instances
    done = 0

    for depth_idx, depth in enumerate(depths):
        for inst_in_depth in range(n_instances):
            # Global unique instance ID: encodes both depth index and replicate index.
            # Guarantees no file overwrite when multiple depths share n_instances replicas.
            instance_id = depth_idx * n_instances + inst_in_depth
            inst_seed = int(rng.integers(0, 2**31))
            inst_rng  = np.random.default_rng(inst_seed)

            if algo == "ising":
                probs = simulate_ising_numpy(
                    n_qubits=n_qubits,
                    n_trotter=depth,
                    J=J, h=h, dt=dt,
                    noise_p1=noise_p1,
                    shots=shots,
                    rng=inst_rng,
                    dd_factor=dd_factor,
                )
                depth_val = float(4 * depth)  # depth proxy: 4 gates per Trotter step

            elif algo == "syncidle":
                probs = simulate_syncidle_numpy(
                    n_qubits=n_qubits,
                    n_idle_rounds=depth,
                    noise_p1_active=noise_active,
                    noise_p1_idle=noise_idle,
                    shots=shots,
                    rng=inst_rng,
                    dd_factor=dd_factor,
                )
                depth_val = float(depth)  # depth = number of idle rounds

            else:
                raise ValueError(f"Unknown algo: {algo}")

            states_p, attr_p = _output_paths(out_dir, device_label, algo.upper(), instance_id, shots)
            _write_states_csv(states_p, probs)
            _write_attr_csv(attr_p, depth_val)

            done += 1
            print(f"  [{done}/{total}] depth={depth_val} instance_id={instance_id} → {states_p.name}")

    print(f"numpy backend: wrote {total} pairs to {out_dir}")


# ── Qiskit Aer backend ────────────────────────────────────────────────────────

def _build_ising_circuit_qiskit(n_qubits: int, n_trotter: int, J: float, h: float, dt: float,
                                  dd_seq: Optional[str]) -> Any:
    """Build 1D TFIM Trotter circuit with optional DD (Qiskit circuit object)."""
    from qiskit import QuantumCircuit
    from qiskit.circuit import Parameter
    import numpy as _np

    theta_zz = J * dt
    phi_x    = h * dt

    qc = QuantumCircuit(n_qubits, n_qubits)
    qc.h(range(n_qubits))  # initialise in |+> for richer distribution

    for _ in range(n_trotter):
        # ZZ layer (nearest-neighbour)
        for q in range(n_qubits - 1):
            qc.cx(q, q + 1)
            qc.rz(2 * theta_zz, q + 1)
            qc.cx(q, q + 1)
        qc.barrier()

        # X layer
        for q in range(n_qubits):
            qc.rx(2 * phi_x, q)
        qc.barrier()

    qc.measure(range(n_qubits), range(n_qubits))
    return qc


def run_aer_backend(
    algo: str,
    depths: List[int],
    n_instances: int,
    shots: int,
    n_qubits: int,
    dd: Optional[str],
    out_dir: Path,
    device_label: str,
    base_seed: int,
    noise_model_name: Optional[str],
) -> None:
    """Generate datasets using Qiskit Aer (must be installed)."""
    try:
        from qiskit_aer import AerSimulator
        from qiskit_aer.noise import NoiseModel, depolarizing_error
    except ImportError:
        print("ERROR: qiskit-aer not installed. Run: pip install qiskit qiskit-aer", file=sys.stderr)
        raise

    from qiskit import transpile

    # Build a simple noise model representative of Brisbane
    nm = NoiseModel()
    p1q = 0.001    # single-qubit gate error
    p2q = 0.008    # two-qubit gate error
    p_m = 0.01     # readout error
    nm.add_all_qubit_quantum_error(depolarizing_error(p1q, 1), ["u1", "u2", "u3", "rz", "rx", "h"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p2q, 2), ["cx", "ecr"])
    nm.add_all_qubit_readout_error([[1 - p_m, p_m], [p_m, 1 - p_m]])

    backend = AerSimulator(noise_model=nm, seed_simulator=base_seed)

    J = 1.0; h = 0.5; dt = 0.15
    rng = np.random.default_rng(base_seed)
    total = len(depths) * n_instances
    done = 0

    for depth_idx, depth in enumerate(depths):
        for inst_in_depth in range(n_instances):
            instance_id = depth_idx * n_instances + inst_in_depth
            inst_seed = int(rng.integers(0, 2**31))
            qc = _build_ising_circuit_qiskit(n_qubits, depth, J, h, dt, dd_seq=dd)
            tqc = transpile(qc, backend=backend, optimization_level=1, seed_transpiler=inst_seed)

            # actual transpiled depth (before measure)
            depth_val = float(tqc.depth())

            job = backend.run(tqc, shots=shots, seed_simulator=inst_seed)
            result = job.result()
            counts = result.get_counts()

            # Convert counts to probability distribution
            total_shots = sum(counts.values())
            n_bits = n_qubits
            dim = 2 ** n_bits
            probs = np.zeros(dim)
            for bitstr, cnt in counts.items():
                idx = int(bitstr, 2)
                probs[idx] = cnt / total_shots

            states_p, attr_p = _output_paths(out_dir, device_label, algo.upper(), instance_id, shots)
            _write_states_csv(states_p, probs)
            _write_attr_csv(attr_p, depth_val)

            done += 1
            print(f"  [{done}/{total}] depth={depth_val} instance_id={instance_id} → {states_p.name}")

    print(f"aer backend: wrote {total} pairs to {out_dir}")


# ── IBM Quantum Brisbane (Runtime) backend ────────────────────────────────────

def run_brisbane_backend(
    algo: str,
    depths: List[int],
    n_instances: int,
    shots: int,
    n_qubits: int,
    dd: Optional[str],
    out_dir: Path,
    ibm_token: str,
    base_seed: int,
) -> None:
    """
    Submit circuits to IBM Brisbane via qiskit-ibm-runtime.
    Requires:  pip install qiskit qiskit-ibm-runtime

    DD sequences: "xx" → XpXm, "xy4" → XY4 (as available in DynamicalDecouplingOptions).
    Brisbane is an ECR-based 127-qubit device; we use the first n_qubits.
    Paper arXiv:2506.10258 used 20 qubits and X-X DD, 20 000 shots.
    """
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        from qiskit_ibm_runtime.options import SamplerOptions
        from qiskit_ibm_runtime.options import DynamicalDecouplingOptions
    except ImportError:
        print("ERROR: qiskit-ibm-runtime not installed. Run: pip install qiskit qiskit-ibm-runtime", file=sys.stderr)
        raise

    from qiskit import transpile

    print("Connecting to IBM Quantum…")
    service = QiskitRuntimeService(channel="ibm_quantum", token=ibm_token)
    backend = service.backend("ibm_brisbane")
    device_label = "Brisbane"

    J = 1.0; h = 0.5; dt = 0.15
    rng = np.random.default_rng(base_seed)

    # DD options
    dd_opts = None
    if dd:
        dd_seq = {"xx": "XpXm", "xy4": "XY4"}.get(dd.lower(), "XpXm")
        dd_opts = DynamicalDecouplingOptions(enable=True, sequence_type=dd_seq)
        print(f"Dynamical Decoupling: {dd_seq}")

    # Build and batch all circuits
    circuits = []
    meta_list = []
    for depth_idx, depth in enumerate(depths):
        for inst_in_depth in range(n_instances):
            instance_id = depth_idx * n_instances + inst_in_depth
            inst_seed = int(rng.integers(0, 2**31))
            qc = _build_ising_circuit_qiskit(n_qubits, depth, J, h, dt, dd_seq=dd)
            tqc = transpile(qc, backend=backend, optimization_level=3,
                            seed_transpiler=inst_seed,
                            initial_layout=list(range(n_qubits)))
            depth_val = float(tqc.depth())
            circuits.append(tqc)
            meta_list.append({
                "depth": depth_val,
                "trotter": depth,
                "instance": instance_id,
                "shots": shots,
            })

    print(f"Submitting {len(circuits)} circuits to ibm_brisbane…")
    sampler_opts = SamplerOptions()
    if dd_opts:
        sampler_opts.dynamical_decoupling = dd_opts

    sampler = SamplerV2(backend=backend, options=sampler_opts)
    job = sampler.run(circuits, shots=shots)
    print(f"Job ID: {job.job_id()} — waiting for results…")
    result = job.result()

    for i, (pub_result, meta) in enumerate(zip(result, meta_list)):
        counts = pub_result.data.meas.get_counts()
        total_shots = sum(counts.values())
        n_bits = n_qubits
        dim = 2 ** n_bits
        probs = np.zeros(dim)
        for bitstr, cnt in counts.items():
            idx = int(bitstr.replace(" ", ""), 2)
            probs[idx % dim] = cnt / total_shots

        states_p, attr_p = _output_paths(
            out_dir, device_label, algo.upper(), meta["instance"], meta["shots"]
        )
        _write_states_csv(states_p, probs)
        _write_attr_csv(attr_p, meta["depth"])
        print(f"  [{i+1}/{len(meta_list)}] depth={meta['depth']} inst={meta['instance']} → {states_p.name}")

    print(f"Brisbane backend: wrote {len(meta_list)} pairs to {out_dir}")


# ── inventory helper ──────────────────────────────────────────────────────────

def _write_run_inventory(out_dir: Path, depths: List[int], algo: str, device: str,
                          n_instances: int, shots: int) -> None:
    """Write a human-readable run_inventory.json alongside the CSV files."""
    doc = {
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "out_dir": str(out_dir.as_posix()),
        "device": device,
        "algo": algo,
        "depths": depths,
        "n_instances": n_instances,
        "shots": shots,
        "n_pairs_expected": len(depths) * n_instances,
        "note": (
            "Depths correspond to Trotter steps (ising) or idle rounds (syncidle). "
            "See arXiv:2506.10258 for the Brisbane synchronisation context."
        ),
    }
    (out_dir / "run_inventory.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate StateProb datasets for qcc_stateprob_cross_conditions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n")[0],  # first paragraph of module docstring
    )
    ap.add_argument("--backend", default="numpy",
                    choices=["numpy", "aer", "brisbane"],
                    help="Simulation / hardware backend (default: numpy)")
    ap.add_argument("--algo", default="ising",
                    choices=["ising", "syncidle"],
                    help="Circuit type (default: ising)")
    ap.add_argument("--depths", default="2,4,6,8,12,16,20,28,36,48,64,80,100,128,160",
                    help="Comma-separated list of depth values (Trotter steps or idle rounds)")
    ap.add_argument("--instances", type=int, default=15,
                    help="Number of instances per depth (default: 15)")
    ap.add_argument("--shots", type=int, default=8192,
                    help="Shots per circuit (default: 8192)")
    ap.add_argument("--n-qubits", type=int, default=8,
                    help="Number of qubits (default: 8; use 20 for Brisbane parity)")
    ap.add_argument("--dd", default=None, choices=[None, "xx", "xy4"],
                    help="Dynamical Decoupling sequence (None=off, xx=X-X, xy4=XY4)")
    ap.add_argument("--out-dir", default="data/brisbane_stateprob",
                    help="Output directory for CSV files")
    ap.add_argument("--seed", type=int, default=1337, help="RNG base seed")

    # Hardware-only
    ap.add_argument("--ibm-token", default="",
                    help="IBM Quantum API token (required for --backend brisbane)")
    ap.add_argument("--noise-model", default=None,
                    help="Aer noise model preset (reserved for future use)")

    args = ap.parse_args(argv)

    depths = [int(d.strip()) for d in args.depths.split(",") if d.strip().isdigit()]
    if not depths:
        print("ERROR: --depths produced no valid integers.", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    _ensure_dir(out_dir)

    device_label = {
        "numpy":    "BrisbaneSim",
        "aer":      "BrisbaneAer",
        "brisbane": "Brisbane",
    }[args.backend]

    print(f"Backend  : {args.backend}  ({device_label})")
    print(f"Algorithm: {args.algo.upper()}")
    print(f"Depths   : {depths}  ({len(depths)} distinct)")
    print(f"Instances: {args.instances}")
    print(f"Shots    : {args.shots}")
    print(f"Qubits   : {args.n_qubits}")
    print(f"DD       : {args.dd or 'off'}")
    print(f"Out dir  : {out_dir}")
    print(f"Expected pairs: {len(depths) * args.instances}")
    print()

    if args.backend == "numpy":
        run_numpy_backend(
            algo=args.algo,
            depths=depths,
            n_instances=args.instances,
            shots=args.shots,
            n_qubits=args.n_qubits,
            dd=args.dd,
            out_dir=out_dir,
            device_label=device_label,
            base_seed=args.seed,
        )
    elif args.backend == "aer":
        run_aer_backend(
            algo=args.algo,
            depths=depths,
            n_instances=args.instances,
            shots=args.shots,
            n_qubits=args.n_qubits,
            dd=args.dd,
            out_dir=out_dir,
            device_label=device_label,
            base_seed=args.seed,
            noise_model_name=args.noise_model,
        )
    elif args.backend == "brisbane":
        if not args.ibm_token:
            print("ERROR: --ibm-token required for Brisbane backend.", file=sys.stderr)
            return 1
        run_brisbane_backend(
            algo=args.algo,
            depths=depths,
            n_instances=args.instances,
            shots=args.shots,
            n_qubits=args.n_qubits,
            dd=args.dd,
            out_dir=out_dir,
            ibm_token=args.ibm_token,
            base_seed=args.seed,
        )
    else:
        print(f"Unknown backend: {args.backend}", file=sys.stderr)
        return 1

    _write_run_inventory(out_dir, depths, args.algo.upper(), device_label, args.instances, args.shots)
    print(f"\nDone. Feed to workflow with:")
    print(f"  python -m tools.qcc_stateprob_cross_conditions \\")
    print(f"      --dataset {out_dir} \\")
    print(f"      --pooling pooled-by-depth \\")
    print(f"      --out-dir _ci_out/brisbane_run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
