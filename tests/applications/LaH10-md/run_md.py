#!/usr/bin/env python3
"""LaH10 300 K / 150 GPa NPT Langevin 模拟辅助脚本."""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch
import yaml
from ase import units
from ase.io import Trajectory, read
from ase.md import MDLogger
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary
from loguru import logger

from mattersim.forcefield import MatterSimCalculator


@dataclass
class OutputPaths:
    workdir: Path
    logfile: Path
    trajectory: Path
    thermo_csv: Path
    restart: Path
    summary: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LaH10 NPT Langevin 模拟配置入口")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("md_config.yaml"),
        help="配置文件路径，默认为当前目录下的 md_config.yaml",
    )
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handler:
        return yaml.safe_load(handler)


def resolve_output_paths(base: Path, raw: Dict[str, Any]) -> OutputPaths:
    workdir = (base / raw.get("workdir", "outputs")).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    return OutputPaths(
        workdir=workdir,
        logfile=workdir / raw.get("logfile", "md.log"),
        trajectory=workdir / raw.get("trajectory", "md.traj"),
        thermo_csv=workdir / raw.get("thermo_csv", "thermo.csv"),
        restart=workdir / raw.get("restart", "md_restart.npz"),
        summary=workdir / raw.get("summary", "md_summary.json"),
    )


def compute_pressure_gpa(atoms) -> float:
    stress = atoms.get_stress(voigt=False)
    pressure = -np.trace(stress) / 3.0
    return pressure * units.GPa


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    base_dir = config_path.parent
    raw_conf = load_config(config_path)

    structure_path = (base_dir / raw_conf["structure_file"]).resolve()
    device = raw_conf.get("device", "cuda")
    if device == "cuda" and not torch.cuda.is_available():
        logger.warning("检测到 CUDA 不可用，自动切换到 CPU 设备")
        device = "cpu"

    rng = np.random.default_rng(raw_conf.get("random_seed", 42))

    sim_conf = raw_conf.get("simulation", {})
    target_temperature = float(sim_conf.get("target_temperature_K", 300.0))
    target_pressure = float(sim_conf.get("target_pressure_GPa", 150.0))
    timestep_fs = float(sim_conf.get("timestep_fs", 0.5))
    total_steps = int(sim_conf.get("total_steps", 20000))
    log_interval = int(sim_conf.get("log_interval", 10))
    traj_interval = int(sim_conf.get("trajectory_interval", 25))
    pressure_interval = int(sim_conf.get("pressure_control_interval", 5))
    restart_interval = int(sim_conf.get("restart_interval", 200))
    friction_timescale = float(sim_conf.get("friction_timescale_fs", 150.0))
    barostat_timescale = float(sim_conf.get("barostat_timescale_fs", 1200.0))
    bulk_modulus = float(sim_conf.get("bulk_modulus_GPa", 220.0))
    ensemble = sim_conf.get("ensemble", "NPT_Langevin")

    output_paths = resolve_output_paths(base_dir, raw_conf.get("output", {}))

    atoms = read(structure_path)
    calc = MatterSimCalculator.from_checkpoint(
        load_path=raw_conf.get("checkpoint", "mattersim-v1.0.0-5m"),
        device=device,
    )
    atoms.calc = calc

    MaxwellBoltzmannDistribution(
        atoms, temperature_K=target_temperature, force_temp=True, rng=rng
    )
    Stationary(atoms)

    friction = 1.0 / (friction_timescale * units.fs)
    dyn = Langevin(
        atoms,
        timestep=timestep_fs * units.fs,
        temperature_K=target_temperature,
        friction=friction,
    )

    log_file = output_paths.logfile.open("w", encoding="utf-8")
    logger.info(
        "MD 运行参数: ensemble=%s, T=%.1f K, P=%.1f GPa, timestep=%.3f fs, steps=%d",
        ensemble,
        target_temperature,
        target_pressure,
        timestep_fs,
        total_steps,
    )

    md_logger = MDLogger(
        dyn,
        atoms,
        log_file,
        header=True,
        stress=True,
        peratom=False,
    )
    dyn.attach(md_logger, interval=log_interval)

    traj = Trajectory(output_paths.trajectory, "w", atoms)
    dyn.attach(traj.write, interval=traj_interval)

    thermo_file = output_paths.thermo_csv.open("w", newline="", encoding="utf-8")
    thermo_writer = csv.writer(thermo_file)
    thermo_writer.writerow(
        [
            "step",
            "time_fs",
            "temperature_K",
            "pressure_GPa",
            "volume_A3",
            "potential_eV",
            "kinetic_eV",
        ]
    )

    pressure_records: list[Dict[str, Any]] = []

    def record_thermo() -> None:
        pressure_gpa = compute_pressure_gpa(atoms)
        thermo_writer.writerow(
            [
                dyn.nsteps,
                dyn.nsteps * timestep_fs,
                dyn.get_temperature(),
                pressure_gpa,
                atoms.get_volume(),
                atoms.get_potential_energy(),
                dyn.get_kinetic_energy(),
            ]
        )
        thermo_file.flush()

    def isotropic_barostat() -> None:
        current_pressure = compute_pressure_gpa(atoms)
        delta = current_pressure - target_pressure
        scale = 1.0 - (timestep_fs / barostat_timescale) * (delta / bulk_modulus)
        scale = clamp(scale, 0.97, 1.03)
        atoms.set_cell(atoms.cell * scale, scale_atoms=True)
        pressure_records.append(
            {
                "step": dyn.nsteps,
                "pressure_GPa": current_pressure,
                "scale": scale,
            }
        )

    def dump_restart() -> None:
        np.savez(
            output_paths.restart,
            step=dyn.nsteps,
            cell=atoms.cell.array,
            positions=atoms.get_positions(),
            momenta=atoms.get_momenta(),
        )

    dyn.attach(record_thermo, interval=log_interval)
    dyn.attach(isotropic_barostat, interval=pressure_interval)
    dyn.attach(dump_restart, interval=restart_interval)

    dyn.run(total_steps)

    log_file.close()
    thermo_file.close()
    traj.close()

    summary = {
        "structure": structure_path.name,
        "ensemble": ensemble,
        "target_temperature_K": target_temperature,
        "target_pressure_GPa": target_pressure,
        "timestep_fs": timestep_fs,
        "total_steps": total_steps,
        "device": device,
        "output": {"directory": str(output_paths.workdir)},
        "pressure_statistics": {
            "samples": pressure_records[-10:],
            "average_GPa": float(
                np.mean([rec["pressure_GPa"] for rec in pressure_records])
            )
            if pressure_records
            else math.nan,
            "std_GPa": float(
                np.std([rec["pressure_GPa"] for rec in pressure_records])
            )
            if pressure_records
            else math.nan,
        },
        "final_cell": atoms.cell.array.tolist(),
    }

    with output_paths.summary.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2)

    logger.info("模拟完成，摘要写入 %s", output_paths.summary)


if __name__ == "__main__":
    main()
