# 团队验证流水线接入审阅交接

本次交付将内部原始源码实际送入团队实现，分别检查源码抽取、切片、Verification Unit、双架构模型目标和原始执行证据。内部原型保留为对照基线；两侧有界 AST 抽取器同源，跨仓库一致性不是完全独立的抽取正确性证明，人工 Oracle 继续单独维护。

## 代码位置与复现

两个仓库的任务分支均为 `feat/internal-pipeline-semantics`。团队仓库保存实际分析实现，本仓库保存内部输入、独立预期、原型基线以及本次新增的接入和核验工具。

| 工作 | 入口 | 用途 |
| --- | --- | --- |
| 原始输入接入 | `scripts/run_team_pipeline.py` | 固定十三例、SB 控制、P02 删除 fence 对照，以及本次重新执行的内部基线 |
| 结构与目标比较 | `scripts/team_pipeline_comparison.py` | 从团队实际 EventIR/VU 和模型矩阵核对人工预期及内部基线 |
| 原始产物核验 | `scripts/team_pipeline_artifacts.py` | 检查 LLVM、VU 交付包、litmus、寄存器映射、原始模型日志与缓存一致性 |
| B02 区域证据 | `scripts/run_benchmark_regions.py`、`scripts/benchmark_region_comparison.py` | 暂存固定源码/include，抽取函数区域，独立比较路径形状、CAS、写回及边界 |

将本仓库与 `RV-MemoryConsistency-TeamDev` 放在同一父目录，配置 Clang/herd7/模型后执行：

```bash
cd RV-MemoryConsistency-TeamDev
python3 -m pytest -q
cd ../Case_Regression_Internal
python3 -m unittest discover -s tests -v
python3 scripts/run_team_pipeline.py --backend local
```

工具位置可通过 `PROTOTYPE_CLANG`、`PROTOTYPE_HERD7`、`PROTOTYPE_X86_MODEL` 和 `PROTOTYPE_RISCV_MODEL` 指定；本机已有 `../.tools/case-regression-env.sh` 时可先 source。完整依赖、参数及输出见[接入说明](TEAM_PIPELINE.md)。

完整集成默认生成团队仓库 `.case-regression-runs/<时间>/` 下的新目录。B01/B02 完整输入尚未支持，整体一致性为 UNKNOWN、退出码为 2 是当前预期边界；应逐项检查十一例、控制及区域比较，不能把这个退出码单独解释为执行故障或全部通过。

## 验证材料与独立性

2026 年 11 月 15 日历史复测为团队 pytest 77 项通过、内部 unittest 153 项通过，无 skip；十一例 C/P 的结构、产物和指定模型目标比较均 PASS。B02 独立函数区域产生 40 条路径，其中 27 条返回、13 条到达边界。这些是历史记录，新整理提交的复测结果另附，不将历史测试冒充当前提交的执行结果。

审阅材料应同时记录两个仓库的提交身份、未提交状态、原始命令及退出码，并提供完整集成摘要、P02 原始和删除 fence 对照的实际产物，以及 B02 区域摘要。大体积原始运行目录与源码提交分开保存；不能仅以缓存中的 PASS 作为证据。

## 已知问题与处理顺序

以下六项由 2026 年 11 月 15 日扫描复现，当前交付未修复：

| 优先级 | 仓库/位置 | 问题 |
| --- | --- | --- |
| P1 | 团队 `frontend/closure.py` | 删除非共享对象上的有序访问可能改变硬件模型结果 |
| P1 | 内部 `scripts/run_correctness.py` | P 系列收集没有强制核对全部必需产物，删除部分 litmus/原始模型日志后仍可能 PASS |
| P2 | 团队 `bounded/engine.py` | static 局部变量存储期处理不正确 |
| P2 | 团队 `src/riscv_litmus.py` | 旧路径寄存器分配存在地址/值冲突 |
| P2 | 团队 `src/cli.py`、`src/verify/herd_runner.py` | 旧 CLI 模型执行失败退出码及超时处理不足 |
| P2 | 内部 `prototype/pipeline.py` 等模型解析入口 | 未严格核对 Observation 的测试身份及错误诊断 |

新增团队产物核验不能替代内部原型自身的证据收集修复。固定十一例通过也不能排除未覆盖的切片和解析边界。完整扫描报告及探针应随内部审阅附件提供，保持问题的复现依据与后续修复状态分离。

优先处理切片和证据可信度，补充相应反向检查，再扩展 B02 完整 main/worker、线程组合和 CAS 模型映射，之后处理 B01 布局、数组、槽位复用与索引环绕。当前 PR 保持 Draft 供阶段性审阅。
