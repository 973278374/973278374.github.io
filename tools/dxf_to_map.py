"""
DXF → map.geojson + nav_graph.json + occupancy.png

图层约定见 docs/CAD图层规范.md
无 DXF 时可用 --demo 生成示意地铁/仓配平面以跑通管线。
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import networkx as nx

try:
    import ezdxf
except ImportError:  # pragma: no cover
    ezdxf = None

LAYER_WALL = "WALL"
LAYER_AISLE = "AISLE"
LAYER_SLOT = "SLOT"
LAYER_DOCK = "DOCK"
LAYER_IGNORE = "IGNORE"


def _poly_to_coords(entity) -> list[list[float]]:
    if entity.dxftype() == "LWPOLYLINE":
        return [[float(p[0]), float(p[1])] for p in entity.get_points("xy")]
    if entity.dxftype() == "POLYLINE":
        return [[float(v.dxf.location.x), float(v.dxf.location.y)] for v in entity.vertices]
    if entity.dxftype() == "CIRCLE":
        cx, cy = float(entity.dxf.center.x), float(entity.dxf.center.y)
        r = float(entity.dxf.radius)
        return [
            [cx + r * math.cos(t), cy + r * math.sin(t)]
            for t in [i * 2 * math.pi / 16 for i in range(16)]
        ]
    return []


def _entity_id(entity, prefix: str) -> str:
    for key in ("ID", "id", "Id"):
        if hasattr(entity, "get_attrib_text") and entity.has_attrib(key):
            return str(entity.get_attrib_text(key)).strip()
    handle = getattr(entity.dxf, "handle", None) or id(entity)
    return f"{prefix}-{handle}"


def parse_dxf(path: Path, unit_scale: float = 1.0) -> dict[str, Any]:
    if ezdxf is None:
        raise RuntimeError("ezdxf 未安装")
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    features: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []

    for ent in msp:
        layer = (ent.dxf.layer or "").upper()
        if layer == LAYER_IGNORE:
            continue
        coords = _poly_to_coords(ent)
        if not coords:
            continue
        coords = [[x * unit_scale, y * unit_scale] for x, y in coords]
        if layer == LAYER_WALL:
            features.append(
                {
                    "type": "Feature",
                    "properties": {"kind": "wall", "layer": layer},
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }
            )
        elif layer == LAYER_AISLE:
            features.append(
                {
                    "type": "Feature",
                    "properties": {"kind": "aisle", "layer": layer},
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }
            )
        elif layer in (LAYER_SLOT, LAYER_DOCK):
            kind = "slot" if layer == LAYER_SLOT else "dock"
            prefix = "SLOT" if kind == "slot" else "DOCK"
            eid = _entity_id(ent, prefix)
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            features.append(
                {
                    "type": "Feature",
                    "properties": {"kind": kind, "id": eid, "layer": layer},
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }
            )
            nodes.append({"id": eid, "kind": kind, "x": cx, "y": cy})

    return {"features": features, "nodes": nodes}


def build_demo_map() -> dict[str, Any]:
    """无 CAD 时的示意仓库：30m x 20m，左右月台 + 中间货位。"""
    features = [
        {
            "type": "Feature",
            "properties": {"kind": "wall"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [30, 0], [30, 20], [0, 20], [0, 0]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"kind": "aisle"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[1, 1], [29, 1], [29, 19], [1, 19], [1, 1]]],
            },
        },
    ]
    nodes = [
        {"id": "DOCK-IN", "kind": "dock", "x": 2.0, "y": 10.0},
        {"id": "DOCK-OUT", "kind": "dock", "x": 28.0, "y": 10.0},
    ]
    # 货位网格
    sid = 1
    for row, y in enumerate([4.0, 10.0, 16.0]):
        for col, x in enumerate([8.0, 12.0, 16.0, 20.0, 24.0]):
            eid = f"SLOT-{sid:02d}"
            sid += 1
            nodes.append({"id": eid, "kind": "slot", "x": x, "y": y})
            features.append(
                {
                    "type": "Feature",
                    "properties": {"kind": "slot", "id": eid},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [x - 1, y - 1],
                                [x + 1, y - 1],
                                [x + 1, y + 1],
                                [x - 1, y + 1],
                                [x - 1, y - 1],
                            ]
                        ],
                    },
                }
            )
    # 通道交叉点
    for i, x in enumerate([5.0, 10.0, 15.0, 20.0, 25.0]):
        for j, y in enumerate([4.0, 10.0, 16.0]):
            nodes.append({"id": f"N-{i}-{j}", "kind": "junction", "x": x, "y": y})
    return {"features": features, "nodes": nodes}


def build_nav_graph(nodes: list[dict[str, Any]], link_radius: float = 6.5) -> dict[str, Any]:
    """按距离阈值连边，生成无向导航图。"""
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], **n)
    ids = [n["id"] for n in nodes]
    pos = {n["id"]: (n["x"], n["y"]) for n in nodes}
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            xa, ya = pos[a]
            xb, yb = pos[b]
            d = math.hypot(xa - xb, ya - yb)
            if d <= link_radius and d > 1e-6:
                G.add_edge(a, b, length=d)
    # 保证 dock 连通：必要时连到最近 junction/slot
    for n in nodes:
        if n["kind"] == "dock" and G.degree(n["id"]) == 0:
            others = [o for o in nodes if o["id"] != n["id"]]
            nearest = min(others, key=lambda o: math.hypot(o["x"] - n["x"], o["y"] - n["y"]))
            d = math.hypot(nearest["x"] - n["x"], nearest["y"] - n["y"])
            G.add_edge(n["id"], nearest["id"], length=d)

    return {
        "nodes": [
            {"id": nid, "x": data["x"], "y": data["y"], "kind": data.get("kind", "junction")}
            for nid, data in G.nodes(data=True)
        ],
        "edges": [
            {"from": u, "to": v, "length": data["length"]}
            for u, v, data in G.edges(data=True)
        ],
    }


def write_occupancy(nodes: list[dict[str, Any]], out_png: Path, scale: float = 10.0) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [n["x"] for n in nodes]
    ys = [n["y"] for n in nodes]
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {"dock": "tab:red", "slot": "tab:blue", "junction": "0.7"}
    for n in nodes:
        ax.scatter(n["x"], n["y"], c=colors.get(n["kind"], "k"), s=40)
        if n["kind"] in ("dock", "slot"):
            ax.annotate(n["id"], (n["x"], n["y"]), fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.set_aspect("equal")
    ax.set_title("nav nodes preview")
    ax.grid(True, alpha=0.3)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def export_all(parsed: dict[str, Any], out_dir: Path, link_radius: float = 6.5) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": parsed["features"]}
    (out_dir / "map.geojson").write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    nav = build_nav_graph(parsed["nodes"], link_radius=link_radius)
    (out_dir / "nav_graph.json").write_text(json.dumps(nav, ensure_ascii=False, indent=2), encoding="utf-8")
    write_occupancy(parsed["nodes"], out_dir / "occupancy.png")
    print(f"wrote {out_dir / 'map.geojson'}")
    print(f"wrote {out_dir / 'nav_graph.json'} nodes={len(nav['nodes'])} edges={len(nav['edges'])}")
    print(f"wrote {out_dir / 'occupancy.png'}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="DXF/demo → map + nav_graph")
    p.add_argument("--input", type=Path, help="DXF 路径")
    p.add_argument("--out", type=Path, default=Path("data/processed"))
    p.add_argument("--unit-scale", type=float, default=1.0, help="毫米图用 0.001")
    p.add_argument("--link-radius", type=float, default=6.5)
    p.add_argument("--demo", action="store_true", help="生成示意地铁图")
    args = p.parse_args(argv)

    if args.demo or not args.input:
        parsed = build_demo_map()
        print("using demo map")
    else:
        parsed = parse_dxf(args.input, unit_scale=args.unit_scale)
    export_all(parsed, args.out, link_radius=args.link_radius)


if __name__ == "__main__":
    main()
