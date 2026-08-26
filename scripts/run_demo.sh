#!/usr/bin/env bash
# Mac M4 / 通用 Unix：一键演示（无 CUDA）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

mkdir -p data/raw data/processed data/output

echo "==> [1/3] build demo map"
python -m tools.dxf_to_map --demo --out data/processed

echo "==> [2/3] path smoke"
python -m tools.path_smoke --graph data/processed/nav_graph.json --src DOCK-IN --dst SLOT-01

echo "==> [3/3] run matrix simulation"
python -m sim.run --scenario scenarios/demo.yaml --out data/output

# 方便 Godot 工程内相对路径读取
mkdir -p godot/data
cp -f data/output/trajectories.json godot/data/trajectories.json
cp -f data/processed/nav_graph.json godot/data/nav_graph.json

echo
echo "OK. KPI: data/output/kpi.json"
echo "Trajectories: data/output/trajectories.json"
echo "Open godot/project.godot in Godot 4 (Apple Silicon) to replay."
