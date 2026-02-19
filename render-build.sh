#!/usr/bin/env bash
# Exit on error
set -o errexit

# Force single-core build to prevent OOM on Render
export CMAKE_BUILD_PARALLEL_LEVEL=1

echo "Installing system dependencies..."
pip install --upgrade pip

echo "Installing requirements with limited concurrency..."
# --no-cache-dir to save space/memory
pip install --no-cache-dir -r requirements.txt
