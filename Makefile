.PHONY: install dev test lint format coverage clean release help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in editable mode
	pip install -e .

dev:  ## Install with dev dependencies
	pip install -e ".[dev]"

test:  ## Run test suite
	PYTHONPATH=04_Code pytest -q

coverage:  ## Run tests with coverage report
	PYTHONPATH=04_Code pytest --cov=src/oric --cov-report=term-missing --cov-report=html

lint:  ## Run linters (flake8 + mypy)
	flake8 src/ 04_Code/pipeline/ --max-line-length=100 --ignore=E501,W503
	mypy src/oric/ --ignore-missing-imports

format:  ## Auto-format code (black + isort)
	black src/ 04_Code/
	isort src/ 04_Code/

demo:  ## Run synthetic demo pipeline
	python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/demo

demo-real:  ## Run real-data pilot (FRED monthly)
	python 04_Code/pipeline/run_real_data_demo.py \
		--input 03_Data/real/fred_monthly/real.csv \
		--outdir 05_Results/real/fred/run_001 \
		--time-mode index --normalize robust_minmax --control-mode no_symbolic

canonical:  ## Run full T1-T8 canonical suite
	python 04_Code/pipeline/run_all_tests.py --outdir 05_Results/canonical

clean:  ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

build:  ## Build distribution packages
	python -m build

release: clean build  ## Build and check before upload
	twine check dist/*
	@echo "Ready to upload. Run: twine upload dist/*"
