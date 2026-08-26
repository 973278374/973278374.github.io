"""冒烟：在 nav_graph 上对 dock→slot 求最短路。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import networkx as nx


def load_graph(path: Path) -> nx.Graph:
    data = json.loads(path.read_text(encoding="utf-8"))
    G = nx.Graph()
    for n in data["nodes"]:
        G.add_node(n["id"], **n)
    for e in data["edges"]:
        G.add_edge(e["from"], e["to"], length=e["length"])
    return G


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, default=Path("data/processed/nav_graph.json"))
    p.add_argument("--src", default="DOCK-IN")
    p.add_argument("--dst", default="SLOT-01")
    args = p.parse_args()
    G = load_graph(args.graph)
    path = nx.shortest_path(G, args.src, args.dst, weight="length")
    length = nx.shortest_path_length(G, args.src, args.dst, weight="length")
    print(" → ".join(path))
    print(f"length_m={length:.2f}")


if __name__ == "__main__":
    main()
