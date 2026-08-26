# 物流矩阵仿真（matrix-sim）

全开源 · 可本地部署 · **面向 Mac M4（Apple Silicon）** · **不使用 CUDA**

基于 CAD 地图做仓配/物流 **OD 矩阵离散事件仿真**，用 Godot 4 做 3D 回放。

## 约束

- 开源组件，本机运行（可断网演示）
- Mac M4：CPU + Metal；禁用 Isaac Sim / CUDA / NVIDIA 依赖
- 逻辑（Python/SimPy）与画面（Godot）解耦

## 快速开始（Mac）

```bash
brew install python@3.12 git
brew install --cask godot blender   # 选 Apple Silicon

cd matrix-sim   # 或本仓库根目录
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

./scripts/run_demo.sh
```

演示会：

1. 用内置示例地图生成导航图  
2. 跑 OD 矩阵仿真  
3. 写出 `data/output/kpi.json` 与 `trajectories.jsonl`

然后用 Godot 4 打开 `godot/project.godot`，运行场景即可回放（需本机已装 Godot）。

## 文档

- [完整技术方案](docs/技术方案-MacM4开源本地矩阵仿真.md)
- [CAD 图层规范](docs/CAD图层规范.md)
- [开源依赖清单](docs/开源依赖清单.md)
- [Godot 接入说明](godot/README.md)

## 目录

```
tools/          CAD → 地图 / 导航图
sim/            SimPy 矩阵仿真引擎
bridge/         本机 FastAPI 调参台
scenarios/      场景与 OD 矩阵
godot/          Godot 4 回放工程
data/           raw / processed / output
scripts/        一键脚本
```

## 常用命令

```bash
# CAD → 地图（将 DXF 放到 data/raw/）
python -m tools.dxf_to_map --input data/raw/plant.dxf --out data/processed

# 跑仿真
python -m sim.run --scenario scenarios/demo.yaml

# 本机 API（仅 127.0.0.1）
python -m bridge.api
```

## 许可证

本仓库示例代码默认 **MIT**（见 `LICENSE`）。第三方依赖各从其许可证。
