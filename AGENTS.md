# Repository Guidelines

## 项目结构与模块组织
MatterSim Python 模块位于 `src/mattersim/`，包含数据准备、神经力场、训练与部署等子包；`tests/` 采用与源代码相同的层级便于精准定位测试；`docs/` 保存 Sphinx 文档与 `docs/_static` 资源，`notebooks/` 用于原型及实验记录，`data/` 与 `pretrained_models/` 提供示例数据和权重；根目录的 `pyproject.toml`、`setup.py` 与 `environment.yaml` 定义依赖、构建参数和可复现环境。

## 构建、测试与开发命令
使用 `mamba env create -f environment.yaml && mamba activate mattersim` 创建基础环境，再运行 `uv pip install -e .` 进入可编辑模式；本地验证使用 `pytest tests`，可附加 `-m "not slow"` 聚焦轻量用例；发布前执行 `pre-commit run --all-files` 以套用 isort、black、flake8；模型微调脚本示例如 `torchrun --nproc_per_node=1 src/mattersim/training/finetune_mattersim.py --load_model_path MatterSim-v1.0.0-1M --train_data_path tests/data/high_level_water.xyz`。

## 编码与命名规范
遵循 Python 3.10+ 语法，统一 4 空格缩进和全面类型注解；模块与函数使用 snake_case，类名采用 PascalCase，测试文件命名 `test_<feature>.py`；保持文档字符串简明描述输入/输出；通过 `black --line-length 88`、`isort --profile black`、`flake8 --max-line-length 88 --ignore E203,W503` 控制风格，必要时补充 `loguru` 日志以追踪关键路径。

## 测试指南
新增功能必须伴随位于 `tests/<module>/` 的单元或集成测试，优先复用 pytest fixture 与参数化以覆盖材料类型、设备和 checkpoint 切换；命令 `pytest tests --maxfail=1 -q --cov=src/mattersim` 用于基线验证，保持关键路径覆盖率不低于 80%，并在 PR 描述中附带结果摘要（通过/失败、设备、主要指标）。

## 提交与拉取请求
所有提交请基于 `mayuan` 分支创建并推送同名远程分支；建议沿用 `ci: ...`、`docs: ...` 等前缀形成 `[scope]: 摘要`，并引用关联 Issue 或讨论；在 `git commit` 前先执行 `pre-commit` 与 `pytest`，PR 模板需包含：变更动机、主要修改点、验证命令输出以及如有 UI/可视内容则附截图或表格；大规模文件（如模型权重）的更新请附下载链接而非直接提交。

## 日志记录与交互规范
每次需求讨论需先整理优化后的提示词、疑问点与执行计划，并将用户问题与助手回应按类别写入 `codexmd/<分类>.md`，分类维度应与本指南章节对应（如“提交流程”“贡献者指南”）；日志内容至少包含时间戳、需求摘要、最终回应与后续动作，必要时引用使用的命令；若需补充新的类别，先在本文件追加说明，再创建对应日志文件保持口径一致。

## 安全与配置提示
Azure 及其他云凭据应放入本地环境变量或密钥管理器，不得写入仓库；`environment.yaml` 包含 GPU 相关依赖，首次安装可使用 `mamba` 或 `micromamba` 加速依赖解析；在 CPU 或 Apple Silicon 平台运行时可显式设置 `device="cpu"` 以规避 MPS 数值抖动，并在实验记录中注明所用设备与 checkpoint 版本。

## 当前交互概览（LaH10 模拟准备）
- 需求要点：① 提交当前除 `deepmd-kit/` 外的所有修改；② 在 `tests/applications/LaH10-md/` 内准备 300 K、150 GPa NPT 模拟所需文件（起始结构位于 `std_H10La_Fm-3m_225_.vasp`）；③ 运行前需列计划并经确认后执行；④ 记录 Langevin NPT 控制策略，并新增“模拟准备”日志分类。
- 执行计划：1) 确认提交范围与记录要求；2) 更新 AGENTS 及日志策略；3) 查阅仓库文档，定位 MD 方法说明；4) 生成 LaH10 NPT 所需结构、脚本、配置与说明；5) 复核所有文件并于 `mayuan` 分支按指定格式提交。
