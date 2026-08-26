"""本机 FastAPI 调参台 — 仅绑定 127.0.0.1，无 CUDA。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sim.engine import MatrixSimulator, SimConfig

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "output"

app = FastAPI(title="matrix-sim local API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    vehicle_count: int = Field(4, ge=1, le=64)
    horizon_s: float = Field(1800, gt=0, le=86400)
    speed_mps: float = Field(1.2, gt=0)
    seed: int = 42
    nav_graph: str = "data/processed/nav_graph.json"
    od_matrix: str = "scenarios/od_matrix.csv"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "cuda": "disabled", "bind": "127.0.0.1"}


@app.post("/api/run")
def run_sim(req: RunRequest) -> dict[str, Any]:
    cfg = SimConfig(
        nav_graph_path=ROOT / req.nav_graph,
        od_matrix_path=ROOT / req.od_matrix,
        vehicle_count=req.vehicle_count,
        speed_mps=req.speed_mps,
        horizon_s=req.horizon_s,
        seed=req.seed,
    )
    kpi, traj = MatrixSimulator(cfg).run()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "kpi.json").write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "trajectories.json").write_text(json.dumps(traj, ensure_ascii=False), encoding="utf-8")
    with (OUTPUT / "trajectories.jsonl").open("w", encoding="utf-8") as f:
        for row in traj:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"kpi": kpi, "trajectory_points": len(traj)}


@app.get("/api/kpi")
def get_kpi() -> Any:
    path = OUTPUT / "kpi.json"
    if not path.exists():
        return {"error": "no kpi; POST /api/run first"}
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/trajectories")
def get_traj() -> Any:
    path = OUTPUT / "trajectories.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    import uvicorn

    uvicorn.run(
        "bridge.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
