# 物流矩阵仿真完整技术方案（全开源 · 本地部署 · Mac M4）

## 1. 目标与约束

### 1.1 目标
- 基于公司现有 **CAD 地图**，搭建可本地运行的 **物流/仓配矩阵仿真**。
- 3D 场景接近真实物理比例与通道拓扑；观感达到 **游戏引擎级实时可视化**（Godot），关键镜头可用 Blender 离线渲染接近宣传片效果。
- 业务上可输出：OD 矩阵吞吐、排队、拥堵热点、资源利用率、轨迹回放。

### 1.2 硬约束
| 约束 | 结论 |
|------|------|
| 全部开源 | 仅用 OSI 友好许可组件（MIT/Apache/GPL 等），不依赖闭源 SaaS |
| 本地部署 | 断网可演示；运行时不依赖云 GPU / 云模型 API |
| Mac M4 | Apple Silicon 原生路径；**不使用 CUDA / Isaac Sim / Omniverse** |
| 公司使用方 | 本机或内网 Mac 即可；不强制 NVIDIA 工作站 |

### 1.3 非目标（本期不做）
- 照片级实时光追数字孪生（需 NVIDIA）
- 精密机器人接触力学（MuJoCo/Isaac 路线）
- 与真实 PLC 硬实时联控（可作二期）

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Mac M4 本机（全本地）                      │
│                                                             │
│  CAD (DXF/DWG→DXF)                                          │
│       │                                                     │
│       ▼                                                     │
│  tools/dxf_to_map.py  →  map.geojson / nav_graph.json       │
│       │                                                     │
│       ▼                                                     │
│  sim/engine.py (SimPy)  →  trajectories + KPI               │
│       │                                                     │
│       ├──────────────►  bridge/api.py (FastAPI localhost)   │
│       │                         │                           │
│       ▼                         ▼                           │
│  Godot 4 (Apple Silicon)  ◄── JSON / WebSocket 回放         │
│       │                                                     │
│       ▼                                                     │
│  （可选）Blender Cycles 离线渲关键镜头                         │
└─────────────────────────────────────────────────────────────┘
```

**原则：逻辑与画面解耦**
- **Python**：算矩阵、事件、路径、指标（权威数据源）
- **Godot**：读轨迹、摆场景、做交互与演示（表现层）
- **Blender/FreeCAD**：资产生成与清洗（内容管线）

---

## 3. 技术选型（已按 M4 / 开源筛过）

| 层级 | 选型 | 许可 | 备注 |
|------|------|------|------|
| CAD 清洗 | FreeCAD / QCAD + `ezdxf` | LGPL / GPL / MIT | DWG 先转 DXF |
| 几何/拓扑 | Shapely, NetworkX | BSD/Apache | 通道图、A* |
| 离散事件仿真 | SimPy | MIT | OD/排队/资源 |
| 本地 API | FastAPI + Uvicorn | MIT | 仅绑定 127.0.0.1 |
| 实时 3D | Godot 4（Apple Silicon） | MIT | 主可视化 |
| 工业仓配扩展（可选） | Open-Industry-Project | 开源 | 货架/传送等资产思路 |
| 建模渲染 | Blender | GPL | glTF 导出；Cycles 离线 |
| 包管理 | Homebrew + Python venv | — | 不依赖 CUDA |

**明确禁用**：CUDA、Isaac Sim、Omniverse、闭源仓配 SaaS、必须以 NVIDIA GPU 为前提的方案。

---

## 4. 数据与「矩阵」定义

### 4.1 地图层
- `walls`：墙体多边形（不可通行）
- `aisles` / `drivable`：可行驶区域
- `slots`：库位/工位（带 ID）
- `docks`：出入口/月台
- `nodes` + `edges`：导航图（交叉口、库位中心、码头）

### 4.2 OD 矩阵
- 行 = 起点（slot/dock ID），列 = 终点 ID
- 单元格 = 单位时间内任务数（或托盘数）
- 支持分时段：`od_matrix_shift_A.csv` 等

### 4.3 仿真实体（默认 AGV/搬运任务）
- Task：从 O 到 D，装卸时间、优先级
- Vehicle：速度、容量、数量
- Resource：月台、电梯、狭窄通道容量

### 4.4 输出 KPI
- 完成量 / 吞吐（tasks/hour）
- 平均等待、最大排队
- 通道边负载（拥堵热力）
- 车辆利用率
- 全量轨迹：`t, vehicle_id, x, y, state`

---

## 5. 实施里程碑（可验收）

### M1 — CAD → 可导航地图
**输入**：车间/仓库 DXF（图层规范见下）  
**输出**：`data/processed/map.geojson`、`nav_graph.json`、`occupancy.png`  
**验收**：命令行 A* 从 dock→slot 有路径；2D 预览图正确

**CAD 图层约定（落地时按此改 CAD）**
| 图层名 | 含义 |
|--------|------|
| WALL | 墙/立柱 |
| AISLE | 通道可行驶 |
| SLOT | 库位（块或闭合多段线，块名/属性含 ID） |
| DOCK | 出入口/月台 |
| IGNORE | 标注、尺寸，脚本跳过 |

### M2 — 无 3D 的矩阵仿真
**输入**：`scenarios/demo.yaml` + `od_matrix.csv` + `nav_graph.json`  
**输出**：`data/output/kpi.json`、`trajectories.jsonl`  
**验收**：改 OD 或车数，KPI 单调合理变化；可复现（固定随机种子）

### M3 — Godot 本地 3D 回放
**输入**：简化 glTF 场景 + 轨迹  
**验收**：Mac 上打开 Godot 工程，车辆按轨迹运动；断网可演示

### M4 — 本地调参台
**输入**：浏览器打开 `http://127.0.0.1:8000`  
**验收**：改车数/OD → 重跑 → Godot 或页内刷新热力

### M5 — 观感增强
- 替换盒子货架为工业简模；Blender 材质；演示相机轨道
- 可选：关键镜头 Cycles 离线渲

---

## 6. Mac M4 环境安装

```bash
# Homebrew
brew install python@3.12 git
brew install --cask blender godot freecad

cd /path/to/matrix-sim
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 一键演示（示例数据，无需真实 CAD）
./scripts/run_demo.sh
```

Apple Silicon 注意：
- Godot / Blender 选择 **Apple Silicon** 构建
- 不要安装 CUDA Toolkit、不要拉 `nvidia-*` 镜像指望 GPU
- 若用 Docker，仅作工具隔离；仿真主路径推荐原生 venv + Godot

---

## 7. 目录结构

```
matrix-sim/
  docs/                 # 本方案与图层规范
  cad/                  # 原始 CAD（gitignore 大文件可选）
  data/
    raw/                # 放入 DXF
    processed/          # geojson / nav_graph
    output/             # 轨迹与 KPI
  scenarios/            # yaml + OD csv
  tools/                # CAD 转换
  sim/                  # SimPy 引擎
  bridge/               # FastAPI
  godot/                # Godot 4 工程
  blender/              # 资产说明与脚本占位
  scripts/              # Mac 一键脚本
  tests/
```

---

## 8. 运行时接口（本地）

### 8.1 轨迹 JSONL（每行一帧或一事件）
```json
{"t": 12.5, "vehicle_id": "AGV-01", "x": 10.2, "y": 3.1, "state": "moving", "task_id": "T-9"}
```

### 8.2 KPI JSON
```json
{
  "completed": 120,
  "throughput_per_hour": 48.0,
  "avg_wait_s": 15.2,
  "edge_load": {"N1-N2": 0.82}
}
```

### 8.3 API（仅本机）
- `POST /api/run` — 跑场景
- `GET /api/kpi` — 最新指标
- `GET /api/trajectories` — 轨迹
- 绑定：`127.0.0.1:8000`

---

## 9. AI 协作方式（公司内可控）

1. **规格先行**：图层名、实体、KPI、场景 yaml 写死再生成代码。
2. **分管道生成**：一次只做 DXF→图 / 仿真 / Godot 胶水之一。
3. **每段验收**：有文件产物 + 测试，再进下一段。
4. **运行时不依赖云模型**：AI 只参与开发，不参与仿真推理闭环。

---

## 10. 风险与对策

| 风险 | 对策 |
|------|------|
| DWG 专有格式 | 统一转 DXF；或 FreeCAD 导出 |
| CAD 线不闭合 | 清洗清单 + 脚本报告未闭合实体 |
| 期望 = 3ds Max 实时画质 | 管理预期：实时 Godot；片子用 Blender |
| 路径与真实不符 | 先校准速度/装卸时间；用真实班次数据反标 |
| 大地图性能 | 导航图稀疏化；Godot 实例化货架；轨迹降采样 |

---

## 11. 二期可选（仍开源、仍可无 CUDA）

- 接内网历史 WMS/TMS 导出 CSV 自动生成 OD
- Godot 编辑器内摆库位的简易工具
- 多人只读演示：内网静态导出 HTML 热力报告（仍无 CUDA）
- 若公司未来采购 NVIDIA 工作站，再评估 Isaac 作「高保真渲染岛」，与本 Python 逻辑层通过轨迹文件对接——**逻辑层无需重写**

---

## 12. 验收清单（项目完工标准）

- [ ] Mac M4 按 README 安装后，`./scripts/run_demo.sh` 成功
- [ ] 自有 DXF 按图层规范可生成 nav_graph
- [ ] 修改 OD/车数可复现不同 KPI
- [ ] Godot 断网可回放轨迹
- [ ] 无任何 CUDA/NVIDIA 运行时依赖
- [ ] 依赖清单与许可证可审计（见 `docs/开源依赖清单.md`）
