# LaH10 NPT Langevin 模拟说明

本目录用于在 300 K、150 GPa 条件下开展 LaH10 的 NPT Langevin 分子动力学模拟，所需结构 `std_H10La_Fm-3m_225_.vasp` 已给出。MatterSim 官方 CLI (`src/mattersim/cli/applications/moldyn.py`) 目前只实现 NVT（Berendsen/ Nose–Hoover）流程，因此这里提供独立脚本以便控制 Langevin 温度和各向同性体积缩放。

## 运行步骤
1. 在 `environment.yaml` 创建的环境中激活 MatterSim，并确保模型权重可通过 `MatterSimCalculator.from_checkpoint` 下载；结构与脚本默认位于 `tests/applications/LaH10-md/`。
2. 根据需要调整 `md_config.yaml`（温度、压力、步长、摩擦与压强松弛时间等）。默认配置：300 K、150 GPa、0.5 fs 步长、20000 步。
3. 执行：
   ```bash
   cd tests/applications/LaH10-md
   python run_md.py --config md_config.yaml
   ```
4. 输出将写入 `output.workdir`（默认 `outputs/`），包括 `*.traj`、`*.log`、`*.csv`、`*_restart.npz` 与 `*_summary.json`，可直接用 ASE、pymatgen 或脚本快速分析。

## 配置项速览
- `structure_file`：起始 POSCAR/VASP 文件，默认即 LaH10 Fm-3m 结构。
- `checkpoint`：MatterSim 模型（`mattersim-v1.0.0-5m` 或 `-1m`）。
- `device`：`cuda` 或 `cpu`，若 GPU 不可用脚本会自动降级。
- `simulation`：
  - `timestep_fs`、`total_steps` 控制时间分辨率与长度；
  - `friction_timescale_fs` 设置 Langevin 摩擦（较小值 → 强耦合）；
  - `barostat_timescale_fs`、`bulk_modulus_GPa` 与 `pressure_control_interval` 定义各向同性体积缩放频率；
  - `target_temperature_K`、`target_pressure_GPa` 指定运行点。
- `output`：自定义工作目录及各类结果文件名。

## 压力控制策略
脚本通过 ASE `Langevin` 演化动量，并在每个 `pressure_control_interval` 步计算瞬时压力（由 `atoms.get_stress` 得到），随后按照 `scale = 1 - ΔP / (B * τ_p / Δt)` 对晶胞作各向同性缩放，近似实现 NPT-Langevin 耦合。Barostat 时间常数与体模量需依据体系调优，新体系时建议先用较大的 `barostat_timescale_fs` 以避免振荡。

## 日志与后处理
`md_300K_150GPa.csv` 记录温度、压力、体积、势能/动能，可用 pandas 快速绘图；`md_300K_150GPa.log` 为 ASE `MDLogger` 产物；`md_300K_150GPa_summary.json` 摘要平均压力与末态晶胞，用于汇报或作为后续计算初始信息；`*_restart.npz` 便于从任意步继续模拟。
