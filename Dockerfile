# ORI-C — Reproducible container image
# Build:   docker build -t oric:latest .
# Run:     docker run --rm -v $(pwd)/05_Results:/app/05_Results oric:latest
FROM python:3.12-slim

LABEL maintainer="Didier Daloze"
LABEL description="Cumulative Symbolic Threshold (ORI-C) — reproducible scientific environment"
LABEL version="1.3.0"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first (layer cache)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install the src/oric package
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Copy the rest of the project
COPY . .

# Create output directory
RUN mkdir -p 05_Results

# Default: run the canonical synthetic demo
CMD ["python", "04_Code/pipeline/run_ori_c_demo.py", "--outdir", "05_Results/demo", "--seed", "42"]
