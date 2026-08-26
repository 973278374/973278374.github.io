"""CLI: python -m sim.run --scenario scenarios/demo.yaml"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sim.engine import MatrixSimulator, config_from_yaml


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Run OD matrix simulation")
    p.add_argument("--scenario", type=Path, default=Path("scenarios/demo.yaml"))
    p.add_argument("--out", type=Path, default=Path("data/output"))
    args = p.parse_args(argv)

    cfg = config_from_yaml(args.scenario)
    sim = MatrixSimulator(cfg)
    kpi, traj = sim.run()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "kpi.json").write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.out / "trajectories.jsonl").open("w", encoding="utf-8") as f:
        for row in traj:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # Godot 友好：整包 JSON
    (args.out / "trajectories.json").write_text(
        json.dumps(traj, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(kpi, ensure_ascii=False, indent=2))
    print(f"trajectories={len(traj)} -> {args.out}")


if __name__ == "__main__":
    main()
