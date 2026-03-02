from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

STATES_RE = re.compile(r"^STATES_(?P<device>.+)_(?P<algo>.+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$", re.IGNORECASE)

def is_missing(x) -> bool:
    if x is None:
        return True
    s = str(x).strip()
    return s == "" or s.lower() == "nan"

def ensure_dataset_dir(dataset: Path, work: Path) -> Path:
    dataset = dataset.resolve()
    if dataset.is_dir():
        return dataset
    if dataset.is_file() and dataset.suffix.lower() == ".zip":
        extract_dir = work / "_dataset_extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dataset, "r") as zf:
            zf.extractall(extract_dir)
        children = [p for p in extract_dir.iterdir() if p.is_dir()]
        return children[0] if len(children) == 1 else extract_dir
    raise FileNotFoundError(f"Dataset path not found or unsupported: {dataset}")

def read_states_csv(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, header=None)
    if df.shape[1] < 2:
        raise ValueError(f"States CSV has <2 cols: {p}")
    df = df.iloc[:, :2].copy()
    df.columns = ["state", "prob"]
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce")
    df = df.dropna(subset=["prob"])
    return df

def read_attr_csv(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    return df

def ccl_from_probs(probs: np.ndarray, metric: str) -> float:
    probs = probs[~np.isnan(probs)]
    probs = probs[probs > 0]
    if probs.size == 0:
        return float("nan")
    probs = probs / probs.sum()
    m = metric.lower().strip()
    if m == "entropy":
        h = float(-(probs * np.log(probs)).sum())
        denom = math.log(probs.size) if probs.size > 1 else 1.0
        return h / denom if denom > 0 else 0.0
    if m == "impurity":
        return float(1.0 - (probs ** 2).sum())
    if m in ("1-max", "1-max_prob", "1-maxprob"):
        return float(1.0 - probs.max())
    raise ValueError(f"Unknown metric: {metric}")

def iter_pairs(dataset_root: Path) -> Iterable[Tuple[Path, Path, Dict[str, str]]]:
    for sp in dataset_root.rglob("State_Probability/*.csv"):
        m = STATES_RE.match(sp.name)
        if not m:
            continue
        meta = m.groupdict()
        device = meta["device"]
        algo = meta["algo"]
        instance = meta["instance"]
        shots = meta["shots"]
        base = sp.parents[1]
        for dname in ("Count_Depth", "Count_Runtime"):
            d = base / dname
            cand = d / f"ATTR_{device}_{algo}_{instance}_{shots}.csv"
            if cand.exists():
                yield sp, cand, meta
                break

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def compute_inventory(dataset_root: Path) -> pd.DataFrame:
    rows = []
    depth_rows = []
    for sp, ap, meta in iter_pairs(dataset_root):
        rows.append({"algo": meta["algo"], "device": meta["device"], "shots": int(meta["shots"]), "instance": int(meta["instance"]), "states": str(sp), "attr": str(ap)})
        adf = read_attr_csv(ap)
        if "Depth" in adf.columns:
            for dv in pd.to_numeric(adf["Depth"], errors="coerce").dropna().unique().tolist():
                depth_rows.append({"algo": meta["algo"], "device": meta["device"], "shots": int(meta["shots"]), "instance": int(meta["instance"]), "depth": float(dv)})
    if not rows:
        return pd.DataFrame(columns=["algo","device","shots","pairs_count","instances_count","depth_distinct_total","depth_distinct_min","depth_distinct_median","depth_distinct_max"])
    df = pd.DataFrame(rows)
    g = df.groupby(["algo","device","shots"], as_index=False).agg(pairs_count=("states","count"), instances_count=("instance","nunique"))
    if not depth_rows:
        g["depth_distinct_total"]=0; g["depth_distinct_min"]=0; g["depth_distinct_median"]=0; g["depth_distinct_max"]=0
        return g.sort_values(["pairs_count","instances_count"], ascending=False)
    ddf = pd.DataFrame(depth_rows)
    g2 = ddf.groupby(["algo","device","shots"], as_index=False).agg(depth_distinct_total=("depth","nunique"))
    per = ddf.groupby(["algo","device","shots","instance"], as_index=False).agg(depth_distinct=("depth","nunique"))
    stats = per.groupby(["algo","device","shots"]).agg(
        depth_distinct_min=("depth_distinct","min"),
        depth_distinct_median=("depth_distinct","median"),
        depth_distinct_max=("depth_distinct","max"),
    ).reset_index()
    out = g.merge(g2, on=["algo","device","shots"], how="left").merge(stats, on=["algo","device","shots"], how="left").fillna(0)
    return out.sort_values(["pairs_count","instances_count","depth_distinct_total"], ascending=False)

def recommend_topk(inv: pd.DataFrame, k: int = 10) -> dict:
    if inv.empty:
        return {"topk": [], "reason": "no pairs found"}
    inv = inv.copy()
    inv["score"] = inv["pairs_count"]*1000 + inv["instances_count"]*100 + inv["depth_distinct_total"]
    top = inv.sort_values(["score","pairs_count","instances_count","depth_distinct_total"], ascending=False).head(k)
    return {"topk": top[["algo","device","shots","pairs_count","instances_count","depth_distinct_total","score"]].to_dict(orient="records"),
            "scoring": "pairs*1000 + instances*100 + depth_total"}

def meta_match(meta: Dict[str,str], algo: str, device: str, shots: str) -> bool:
    if not is_missing(algo) and meta["algo"].lower() != algo.lower():
        return False
    if not is_missing(device) and device.lower() not in meta["device"].lower():
        return False
    if not is_missing(shots):
        try:
            s = int(str(shots).strip())
        except Exception:
            return False
        if int(meta["shots"]) != s:
            return False
    return True

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--algo", default="")
    ap.add_argument("--device", default="")
    ap.add_argument("--shots", default="")
    ap.add_argument("--t-axis", default="Depth", choices=["Depth","Runtime"])
    ap.add_argument("--metric", default="entropy", choices=["entropy","impurity","1-max"])
    ap.add_argument("--threshold", default="0.70")
    ap.add_argument("--bootstrap", default="500")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    run_dir = out_root / "runs" / datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    (run_dir/"tables").mkdir(parents=True, exist_ok=True)
    (run_dir/"figures").mkdir(parents=True, exist_ok=True)
    (run_dir/"contracts").mkdir(parents=True, exist_ok=True)
    work = run_dir / "_work"
    work.mkdir(parents=True, exist_ok=True)

    dataset_root = ensure_dataset_dir(Path(args.dataset), work)

    inv = compute_inventory(dataset_root)
    inv.to_csv(run_dir/"tables/inventory.csv", index=False)
    (run_dir/"tables/recommendations.json").write_text(json.dumps(recommend_topk(inv,10), indent=2), encoding="utf-8")

    rows=[]
    for sp, apath, meta in iter_pairs(dataset_root):
        if not meta_match(meta, args.algo, args.device, args.shots):
            continue
        s_df = read_states_csv(sp)
        a_df = read_attr_csv(apath)
        tcol = args.t_axis
        if tcol not in a_df.columns:
            continue
        tvals = pd.to_numeric(a_df[tcol], errors="coerce").dropna()
        if tvals.empty:
            continue
        t=float(tvals.iloc[0])
        ccl=ccl_from_probs(s_df["prob"].to_numpy(), args.metric)
        rows.append({"algo": meta["algo"], "device": meta["device"], "shots": int(meta["shots"]), "instance": int(meta["instance"]), "t": t, "ccl": ccl})
    df=pd.DataFrame(rows)
    df.to_csv(run_dir/"tables/ccl_points.csv", index=False)

    thr=float(args.threshold); boot=int(args.bootstrap)

    if df.empty:
        pd.DataFrame(columns=["shots","t","ccl_mean","ccl_n"]).to_csv(run_dir/"tables/ccl_by_shots.csv", index=False)
        pd.DataFrame(columns=["shots","tstar"]).to_csv(run_dir/"tables/tstar_by_shots.csv", index=False)
        pd.DataFrame(columns=["shots","bootstrap_sample","tstar"]).to_csv(run_dir/"tables/bootstrap_tstar_by_shots.csv", index=False)
        plt.figure(); plt.text(0.5,0.5,"No data after filters", ha="center"); plt.axis("off")
        plt.savefig(run_dir/"figures/ccl_vs_axis_by_shots.png", dpi=160); plt.close()
    else:
        agg=df.groupby(["shots","t"], as_index=False).agg(ccl_mean=("ccl","mean"), ccl_n=("ccl","count")).sort_values(["shots","t"])
        agg.to_csv(run_dir/"tables/ccl_by_shots.csv", index=False)

        tstars=[]
        for shots, g in agg.groupby("shots"):
            g=g.sort_values("t")
            crossed=g[g["ccl_mean"]>=thr]
            tstars.append({"shots": int(shots), "tstar": float(crossed.iloc[0]["t"]) if not crossed.empty else float("nan")})
        pd.DataFrame(tstars).to_csv(run_dir/"tables/tstar_by_shots.csv", index=False)

        boot_rows=[]
        for shots in sorted(df["shots"].unique()):
            sub=df[df["shots"]==shots].dropna(subset=["t","ccl"])
            if sub.empty:
                continue
            t_vals=sorted(sub["t"].unique())
            per_t={t: sub[sub["t"]==t]["ccl"].to_numpy() for t in t_vals}
            for b in range(boot):
                means=[]
                for t in t_vals:
                    arr=per_t[t]
                    samp=np.random.choice(arr, size=arr.size, replace=True) if arr.size else np.array([np.nan])
                    means.append((t, float(np.nanmean(samp))))
                means.sort(key=lambda x:x[0])
                tstar=float("nan")
                for t, m in means:
                    if not math.isnan(m) and m>=thr:
                        tstar=float(t); break
                boot_rows.append({"shots": int(shots), "bootstrap_sample": b, "tstar": tstar})
        pd.DataFrame(boot_rows).to_csv(run_dir/"tables/bootstrap_tstar_by_shots.csv", index=False)

        plt.figure()
        for shots, g in agg.groupby("shots"):
            plt.plot(g["t"], g["ccl_mean"], marker="o", label=f"shots={int(shots)} (n={int(g['ccl_n'].sum())})")
        plt.axhline(thr, linestyle="--")
        plt.xlabel(args.t_axis); plt.ylabel(f"Ccl ({args.metric})")
        plt.title("Ccl vs axis by shots (pooled)")
        plt.legend(); plt.tight_layout()
        plt.savefig(run_dir/"figures/ccl_vs_axis_by_shots.png", dpi=160); plt.close()

    contract={
        "dataset_path": args.dataset,
        "dataset_mode": "zip-or-dir",
        "filters": {"algo": args.algo, "device": args.device, "shots": args.shots},
        "t_axis": args.t_axis,
        "ccl_metric": args.metric,
        "threshold": thr,
        "tstar_rule": "first t where pooled mean Ccl >= threshold",
        "bootstrap_samples": boot,
        "no_verdict": True,
        "note": "Cross-conditions view: compare Ccl vs axis across shots. No algorithm success judgement. No Sigma."
    }
    (run_dir/"contracts/mapping_cross_conditions.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

    items=[]
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            rel=str(p.relative_to(run_dir)).replace("\\","/")
            items.append({"path": rel, "sha256": sha256_file(p), "bytes": p.stat().st_size})
    (run_dir/"manifest.json").write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")

    try:
        shutil.rmtree(work)
    except Exception:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
