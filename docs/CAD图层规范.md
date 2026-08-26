# CAD 图层规范

仿真管线只认约定图层名。导入前请在 CAD 中整理图层。

## 必须图层

| 图层名 | 几何 | 说明 |
|--------|------|------|
| `WALL` | 闭合多段线 / 线 | 墙、立柱；不可通行 |
| `AISLE` | 闭合多段线 | 可行驶区域（若缺失则用画布减 WALL 近似） |
| `SLOT` | 闭合多段线或块 | 库位；需稳定 ID |
| `DOCK` | 闭合多段线或块 | 月台 / 出入口 |

## 可选图层

| 图层名 | 说明 |
|--------|------|
| `IGNORE` | 标注、尺寸、图框；脚本跳过 |
| `KEEP_OUT` | 禁行区 |
| `ONE_WAY` | 单行道中心线（进阶） |

## ID 规则

- `SLOT` / `DOCK`：优先读块属性 `ID`；否则用实体句柄生成 `SLOT-xxxx`
- ID 全局唯一，OD 矩阵的行列名必须与此一致

## 单位与坐标

- 单位：**米**（若 CAD 为毫米，在 `scenarios/*.yaml` 设 `unit_scale: 0.001`）
- 原点：建议图纸左下为 (0,0)，Y 向上
- Z：平面仿真用 2D；Godot 中墙高默认 3.0 m 拉伸

## DWG 处理

1. 用 FreeCAD / ODA 等转为 **DXF R2010+**
2. 放入 `data/raw/`
3. 执行 `python -m tools.dxf_to_map ...`

## 验收

转换后检查：

- [ ] `map.geojson` 含 wall/slot/dock
- [ ] `nav_graph.json` 节点数 > 0 且连通
- [ ] 任选 dock→slot，`tools.path_smoke.py` 能出路径
