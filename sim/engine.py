"""
OD 矩阵离散事件仿真（SimPy，纯 CPU，无 CUDA）。

车辆从 OD 矩阵抽样任务，沿 nav_graph 最短路行驶，统计 KPI 与轨迹。
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import simpy


@dataclass
class SimConfig:
    nav_graph_path: Path
    od_matrix_path: Path
    vehicle_count: int = 4
    speed_mps: float = 1.2
    load_time_s: float = 20.0
    unload_time_s: float = 20.0
    horizon_s: float = 3600.0
    seed: int = 42
    trajectory_dt: float = 1.0
    arrival_mean_s: float = 30.0


@dataclass
class KPI:
    completed: int = 0
    total_wait_s: float = 0.0
    wait_samples: int = 0
    edge_load: dict[str, float] = field(default_factory=dict)
    vehicle_busy_s: dict[str, float] = field(default_factory=dict)

    def to_dict(self, horizon_s: float) -> dict[str, Any]:
        avg_wait = self.total_wait_s / self.wait_samples if self.wait_samples else 0.0
        throughput = self.completed / (horizon_s / 3600.0) if horizon_s > 0 else 0.0
        util = {
            vid: busy / horizon_s if horizon_s > 0 else 0.0
            for vid, busy in self.vehicle_busy_s.items()
        }
        return {
            "completed": self.completed,
            "throughput_per_hour": round(throughput, 2),
            "avg_wait_s": round(avg_wait, 2),
            "edge_load": {k: round(v, 3) for k, v in sorted(self.edge_load.items())},
            "vehicle_utilization": {k: round(v, 3) for k, v in util.items()},
        }


def load_nav_graph(path: Path) -> nx.Graph:
    data = json.loads(path.read_text(encoding="utf-8"))
    G = nx.Graph()
    for n in data["nodes"]:
        G.add_node(n["id"], x=n["x"], y=n["y"], kind=n.get("kind", "junction"))
    for e in data["edges"]:
        G.add_edge(e["from"], e["to"], length=float(e["length"]))
    return G


def load_od_pairs(path: Path) -> list[tuple[str, str, float]]:
    """
    CSV: origin,destination,rate_per_hour
    或矩阵表头为节点 ID。
    """
    import pandas as pd

    df = pd.read_csv(path)
    cols = [c.lower() for c in df.columns]
    if {"origin", "destination", "rate_per_hour"} <= set(cols):
        rename = {c: c.lower() for c in df.columns}
        df = df.rename(columns=rename)
        return [
            (str(r.origin), str(r.destination), float(r.rate_per_hour))
            for r in df.itertuples(index=False)
        ]
    # 矩阵形式
    df = df.set_index(df.columns[0])
    pairs: list[tuple[str, str, float]] = []
    for o in df.index:
        for d in df.columns:
            val = float(df.loc[o, d])
            if val > 0 and str(o) != str(d):
                pairs.append((str(o), str(d), val))
    return pairs


class MatrixSimulator:
    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.G = load_nav_graph(cfg.nav_graph_path)
        self.od_pairs = load_od_pairs(cfg.od_matrix_path)
        self.kpi = KPI()
        self.trajectories: list[dict[str, Any]] = []
        self.env = simpy.Environment()
        self.idle_vehicles: simpy.Store = simpy.Store(self.env)
        self.task_queue: simpy.Store = simpy.Store(self.env)

    def _edge_key(self, a: str, b: str) -> str:
        return f"{a}-{b}" if a <= b else f"{b}-{a}"

    def _path(self, src: str, dst: str) -> list[str]:
        return nx.shortest_path(self.G, src, dst, weight="length")

    def _emit(self, vehicle_id: str, x: float, y: float, state: str, task_id: str | None = None) -> None:
        self.trajectories.append(
            {
                "t": round(float(self.env.now), 3),
                "vehicle_id": vehicle_id,
                "x": round(x, 3),
                "y": round(y, 3),
                "state": state,
                "task_id": task_id,
            }
        )

    def _move_along(self, vehicle_id: str, path: list[str], task_id: str):
        cfg = self.cfg
        for a, b in zip(path, path[1:]):
            ax, ay = self.G.nodes[a]["x"], self.G.nodes[a]["y"]
            bx, by = self.G.nodes[b]["x"], self.G.nodes[b]["y"]
            length = float(self.G[a][b]["length"])
            key = self._edge_key(a, b)
            self.kpi.edge_load[key] = self.kpi.edge_load.get(key, 0.0) + length
            travel = length / cfg.speed_mps
            steps = max(1, int(travel / cfg.trajectory_dt))
            for i in range(1, steps + 1):
                yield self.env.timeout(travel / steps)
                u = i / steps
                x, y = ax + (bx - ax) * u, ay + (by - ay) * u
                self._emit(vehicle_id, x, y, "moving", task_id)
                self.kpi.vehicle_busy_s[vehicle_id] = self.kpi.vehicle_busy_s.get(vehicle_id, 0.0) + (
                    travel / steps
                )

    def task_generator(self):
        """按 OD 小时率泊松到达。"""
        # 归一化为总到达率
        total_rate = sum(r for _, _, r in self.od_pairs)  # per hour
        if total_rate <= 0:
            return
        mean_inter = 3600.0 / total_rate
        weights = [r for _, _, r in self.od_pairs]
        task_i = 0
        while self.env.now < self.cfg.horizon_s:
            gap = self.rng.expovariate(1.0 / mean_inter)
            yield self.env.timeout(gap)
            o, d, _ = self.rng.choices(self.od_pairs, weights=weights, k=1)[0]
            task_i += 1
            yield self.task_queue.put(
                {"id": f"T-{task_i}", "origin": o, "destination": d, "created": self.env.now}
            )

    def vehicle_proc(self, vehicle_id: str):
        # 初始停在 DOCK-IN 或第一个 dock
        docks = [n for n, d in self.G.nodes(data=True) if d.get("kind") == "dock"]
        home = "DOCK-IN" if "DOCK-IN" in self.G else (docks[0] if docks else next(iter(self.G.nodes)))
        x0, y0 = self.G.nodes[home]["x"], self.G.nodes[home]["y"]
        self._emit(vehicle_id, x0, y0, "idle", None)
        self.kpi.vehicle_busy_s.setdefault(vehicle_id, 0.0)

        while self.env.now < self.cfg.horizon_s:
            task = yield self.task_queue.get()
            wait = self.env.now - task["created"]
            self.kpi.total_wait_s += wait
            self.kpi.wait_samples += 1
            tid = task["id"]
            try:
                to_pick = self._path(home, task["origin"])
            except nx.NetworkXNoPath:
                self._emit(vehicle_id, x0, y0, "no_path", tid)
                continue
            yield from self._move_along(vehicle_id, to_pick, tid)
            yield self.env.timeout(self.cfg.load_time_s)
            self.kpi.vehicle_busy_s[vehicle_id] += self.cfg.load_time_s
            ox, oy = self.G.nodes[task["origin"]]["x"], self.G.nodes[task["origin"]]["y"]
            self._emit(vehicle_id, ox, oy, "loading", tid)

            try:
                to_drop = self._path(task["origin"], task["destination"])
            except nx.NetworkXNoPath:
                home = task["origin"]
                x0, y0 = ox, oy
                continue
            yield from self._move_along(vehicle_id, to_drop, tid)
            yield self.env.timeout(self.cfg.unload_time_s)
            self.kpi.vehicle_busy_s[vehicle_id] += self.cfg.unload_time_s
            dx, dy = (
                self.G.nodes[task["destination"]]["x"],
                self.G.nodes[task["destination"]]["y"],
            )
            self._emit(vehicle_id, dx, dy, "unloading", tid)
            self.kpi.completed += 1
            home = task["destination"]
            x0, y0 = dx, dy
            self._emit(vehicle_id, x0, y0, "idle", None)

    def run(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        self.env.process(self.task_generator())
        for i in range(self.cfg.vehicle_count):
            vid = f"AGV-{i + 1:02d}"
            self.env.process(self.vehicle_proc(vid))
        self.env.run(until=self.cfg.horizon_s)
        # normalize edge_load to relative
        if self.kpi.edge_load:
            m = max(self.kpi.edge_load.values()) or 1.0
            self.kpi.edge_load = {k: v / m for k, v in self.kpi.edge_load.items()}
        return self.kpi.to_dict(self.cfg.horizon_s), self.trajectories


def config_from_yaml(path: Path) -> SimConfig:
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = path.parent.parent
    return SimConfig(
        nav_graph_path=(base / raw["nav_graph"]).resolve(),
        od_matrix_path=(base / raw["od_matrix"]).resolve(),
        vehicle_count=int(raw.get("vehicle_count", 4)),
        speed_mps=float(raw.get("speed_mps", 1.2)),
        load_time_s=float(raw.get("load_time_s", 20)),
        unload_time_s=float(raw.get("unload_time_s", 20)),
        horizon_s=float(raw.get("horizon_s", 3600)),
        seed=int(raw.get("seed", 42)),
        trajectory_dt=float(raw.get("trajectory_dt", 1.0)),
        arrival_mean_s=float(raw.get("arrival_mean_s", 30)),
    )
