.PHONY: install dev test lint format coverage clean release help \
        smoke real-smoke collect canonical-qcc local-run-sample \
        replicate benchmark-pilots densify-pilots

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in editable mode
	pip install -e .

dev:  ## Install with dev dependencies
	pip install -e ".[dev]"

test:  ## Run test suite
	pytest -q

coverage:  ## Run tests with coverage report
	pytest --cov=src/oric --cov-report=term-missing --cov-report=html

lint:  ## Run linters (ruff + mypy)
	ruff check .
	ruff format --check .
	mypy src/oric/ --ignore-missing-imports

format:  ## Auto-format code (ruff)
	ruff check --fix .
	ruff format .

demo:  ## Run synthetic demo pipeline
	python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/demo

demo-real:  ## Run real-data pilot (FRED monthly)
	python 04_Code/pipeline/run_real_data_demo.py \
		--input 03_Data/real/fred_monthly/real.csv \
		--outdir 05_Results/real/fred/run_001 \
		--time-mode index --normalize robust_minmax --control-mode no_symbolic

canonical:  ## Run full T1-T8 canonical suite
	python 04_Code/pipeline/run_all_tests.py --outdir 05_Results/canonical

# ── ORI-C one-liners ──────────────────────────────────────────────────────────

smoke:  ## Smoke CI: run real-data smoke matrix (1 dataset/sector, fast)
	@echo "Running real data smoke matrix (1 dataset per sector)..."
	@python -m tools.run_real_smoke_matrix

real-smoke:  ## Alias for smoke (real data smoke gate)
	$(MAKE) smoke

canonical-qcc:  ## Run QCC canonical full pipeline locally (numpy backend, fast params)
	@echo "Running QCC canonical full (numpy, scan_only for local speed)..."
	@python -m tools.generate_brisbane_stateprob \
		--backend numpy --algo ising \
		--depths 2,4,6,8,12,16 --instances 5 --shots 1024 --n-qubits 4 --seed 1337 \
		--out-dir _ci_out/qcc_canonical_local/data
	@python -m tools.qcc_stateprob_cross_conditions \
		--dataset _ci_out/qcc_canonical_local/data \
		--out-dir _ci_out/qcc_canonical_local \
		--pooling pooled-by-depth --metric entropy --threshold 0.70 \
		--bootstrap-samples 100 --seed 1337 --power-criteria contracts/POWER_CRITERIA.json \
		--auto-plan
	@python -m tools.stage_contracts \
		--out-root _ci_out/qcc_canonical_local \
		--power-criteria contracts/POWER_CRITERIA.json \
		--stability-criteria contracts/STABILITY_CRITERIA.json
	@python -m tools.qcc_stateprob_write_manifest --out-root _ci_out/qcc_canonical_local
	@python -m tools.verify_audit_invariants --out-root _ci_out/qcc_canonical_local --no-stability
	@echo "QCC local scan complete. Results: _ci_out/qcc_canonical_local/"

collect:  ## Collect CI metrics from _collected_artifacts/ into ci_metrics/
	@echo "Collecting CI metrics from _collected_artifacts/ ..."
	@python -m tools.collect_ci_metrics \
		--in-dir _collected_artifacts \
		--out-dir ci_metrics \
		--append
	@echo "Done. See ci_metrics/runs_index.csv and ci_metrics/history.csv"

local-run-sample:  ## Reproduce minimal sample run with expected outputs
	@echo "Running local reproducible sample (data/climate/co2_mm_mlo.csv)..."
	@python - <<'EOF'
	import csv, hashlib, json, shutil, subprocess, sys
	from datetime import datetime
	from pathlib import Path
	
	dataset = Path("data/climate/co2_mm_mlo.csv")
	if not dataset.exists():
	    print(f"ERROR: {dataset} not found. Check data/climate/", file=sys.stderr)
	    sys.exit(1)
	
	ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
	run_dir = Path(f"_ci_out/local_sample/runs/{ts}")
	for sub in ("tables", "figures", "contracts"):
	    (run_dir / sub).mkdir(parents=True, exist_ok=True)
	
	shutil.copy("contracts/POWER_CRITERIA.json", run_dir / "contracts/")
	shutil.copy("contracts/STABILITY_CRITERIA.json", run_dir / "contracts/")
	
	h = hashlib.sha256(dataset.read_bytes()).hexdigest()
	with open(run_dir / "contracts/input_inventory.csv", "w") as f:
	    w = csv.DictWriter(f, fieldnames=["file", "sha256", "size_bytes"])
	    w.writeheader()
	    w.writerow({"file": str(dataset), "sha256": h, "size_bytes": dataset.stat().st_size})
	
	summary = {
	    "dataset_id": "co2_mauna_loa",
	    "sector": "climate",
	    "run_mode": "smoke",
	    "dataset_path": str(dataset),
	}
	(run_dir / "tables/summary.json").write_text(json.dumps(summary, indent=2))
	(run_dir / "figures/placeholder.txt").write_text("local sample run")
	
	subprocess.run([
	    sys.executable, "-m", "tools.make_manifest",
	    "--root", str(run_dir), "--out", str(run_dir / "manifest.json"),
	], check=True)
	subprocess.run([
	    sys.executable, "-m", "tools.enforce_output_contract", "--run-dir", str(run_dir),
	], check=True)
	
	print(f"\nSample run complete: {run_dir}")
	print("Expected files: tables/summary.json, contracts/POWER_CRITERIA.json,")
	print("                contracts/STABILITY_CRITERIA.json, contracts/input_inventory.csv,")
	print("                figures/placeholder.txt, manifest.json")
	EOF

replicate:  ## Run external replication protocol (verifies frozen params, tests, pilots, matrix)
	PYTHONPATH=src:04_Code python tools/replicate.py --outdir replication_output

benchmark-pilots:  ## Run comparative benchmark on BTC, EEG Bonn, Solar
	PYTHONPATH=src:04_Code python -c "from pathlib import Path; from oric.comparative_benchmark import run_all_benchmarks; r = run_all_benchmarks(Path('05_Results/pilots'), pilots=[{'pilot_id':'sector_finance.pilot_btc','csv':'03_Data/sector_finance/real/pilot_btc/real.csv','verdict':'ACCEPT'},{'pilot_id':'sector_neuro.pilot_eeg_bonn','csv':'03_Data/sector_neuro/real/pilot_eeg_bonn/real.csv','verdict':'ACCEPT'},{'pilot_id':'sector_cosmo.pilot_solar','csv':'03_Data/sector_cosmo/real/pilot_solar/real.csv','verdict':'ACCEPT'}]); print(f\"Benchmarked {r['total_pilots']} pilots across {len(r['methods'])} methods\")"

densify-pilots:  ## Run densification on 3 underpowered pilots
	PYTHONPATH=src:04_Code python 04_Code/pipeline/densify_underpowered_pilots.py --outdir 05_Results/pilots/power_upgrade

clean:  ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

build:  ## Build distribution packages
	python -m build

release: clean build  ## Build and check before upload
	twine check dist/*
	@echo "Ready to upload. Run: twine upload dist/*"
