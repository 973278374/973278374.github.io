from __future__ import annotations

from pathlib import Path

from tools.dxf_to_map import build_demo_map, build_nav_graph, export_all
from sim.engine import MatrixSimulator, SimConfig


def test_demo_nav_and_sim(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    export_all(build_demo_map(), processed, link_radius=6.5)
    nav = processed / "nav_graph.json"
    assert nav.exists()

    # write tiny od next to tmp
    od = tmp_path / "od.csv"
    od.write_text(
        "origin,destination,rate_per_hour\nDOCK-IN,SLOT-01,30\nSLOT-01,DOCK-OUT,30\n",
        encoding="utf-8",
    )
    cfg = SimConfig(
        nav_graph_path=nav,
        od_matrix_path=od,
        vehicle_count=2,
        horizon_s=300,
        speed_mps=2.0,
        load_time_s=5,
        unload_time_s=5,
        seed=1,
        trajectory_dt=2.0,
    )
    kpi, traj = MatrixSimulator(cfg).run()
    assert kpi["completed"] >= 1
    assert len(traj) > 10


def test_nav_graph_has_docks() -> None:
    parsed = build_demo_map()
    nav = build_nav_graph(parsed["nodes"])
    kinds = {n["kind"] for n in nav["nodes"]}
    assert "dock" in kinds and "slot" in kinds
    assert len(nav["edges"]) > 0
