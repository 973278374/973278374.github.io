# Godot 4 本地回放

## 前置
1. 安装 **Godot 4.x Apple Silicon**（`brew install --cask godot`）
2. 在仓库根目录执行 `./scripts/run_demo.sh`，生成 `data/output/trajectories.json`

## 打开
1. 启动 Godot → Import / Open `godot/project.godot`
2. 运行主场景 `scenes/main.tscn`（F5）

## 说明
- 仿真坐标 `(x, y)` 映射为 Godot `(X, Z)`，Y 向上为高度
- 不依赖 CUDA / NVIDIA
- 轨迹文件过大时可在 `scenarios/demo.yaml` 增大 `trajectory_dt` 降采样

## 换自有 CAD
1. 按 `docs/CAD图层规范.md` 整理 DXF  
2. `python -m tools.dxf_to_map --input data/raw/plant.dxf`  
3. 重跑仿真后回到本工程回放  
4. （可选）用 Blender 做墙体/货架 glTF，替换默认盒子
