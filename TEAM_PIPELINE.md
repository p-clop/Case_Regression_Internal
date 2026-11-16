# 接入团队 Verification Pipeline

## 用途与入口

`scripts/run_team_pipeline.py` 将固定清单中的 C01–C08、P01–P03 和 B01/B02 原始源码实际送入 `RV-MemoryConsistency-TeamDev/verification_pipeline`，检查调用、能力边界和可比较的输出，同时新运行内部验证作为对照。C/P 系列使用显式 `--semantics hardware-projection`，已支持这十一例的有界结构与原始硬件目标；B01/B02 仍为 UNSUPPORTED。SB 正向控制和 P02 删除 fence 对照另外计数。

```bash
cd /home/zhovy/work/Case_Regression_Internal
python3 scripts/run_team_pipeline.py
```

默认团队仓库为同级的 `RV-MemoryConsistency-TeamDev`。Clang 优先使用命令参数、`PROTOTYPE_CLANG` 或同级 `.tools/clang18/bin/clang`；herd7 使用参数、`PROTOTYPE_HERD7` 或既有安装。模型可用 `--x86-model`、`--riscv-model` 或原有 `PROTOTYPE_*` 环境变量指定，也可沿用 `source ../.tools/case-regression-env.sh`。

```bash
python3 scripts/run_team_pipeline.py \
  --team-root ../RV-MemoryConsistency-TeamDev \
  --backend local \
  --out ../RV-MemoryConsistency-TeamDev/.case-regression-runs/manual-run
```

`--out` 必须是团队 worktree 内尚不存在的新路径。默认在团队仓库的 `.case-regression-runs/<上海时间>/` 保存证据；该目录由团队仓库 `.gitignore` 忽略。执行过程中打印每例状态，最终打印报告路径。该流程不安装工具。

## 执行与比较

驱动器读取 `correctness_manifest.json`，要求十三例完整且唯一。每次运行按原相对路径复制源码、Oracle、说明以及 Benchmark 的 `common/`、`vendor/` 依赖，逐文件验证 SHA256；输入进入团队 worktree 后调用 `python3 -m verification_pipeline --source ... --out ...`。不改写原始 case，也不删掉 fence、循环或 CAS 来绕过能力检查。

驱动器将 C/P Oracle 声明的 seed 作为 `--seed-object` 查询配置，并将原始模型目标以 `--queries` 交给团队后端；查询文件不包含预期 Sometimes/Never。C 系列读取各自 `architecture.json` 中无注入 fence 的原始目标，包括写值域之外的禁止读值。P02 另在独立目录生成删除 fence 的派生对照，要求两架构恢复 Sometimes，不计作原始输入的结果。

SB 控制使用独立的 `tests/team_pipeline/sb.c` 和人工预期 `sb.expected.json`。它包含两个线程、两个全局 relaxed atomic int、四个事件；预期一个 VU 保留全部事件和两个对象，四种读值组合在 x86-TSO/RVWMO 下均为 Sometimes。比较覆盖对象/初值、线程事件序列、program order、VU 成员和四组双架构查询。控制例不算作原始十三例中的任何一例。

随后运行独立的 B02 函数区域证据层，再调用 `scripts/run_correctness.py --out <本次目录>/baseline`，新运行内部结构、P 系列模型、Benchmark 与 C 系列架构检查。Baseline 的分层报告、原生轨迹、负向对照和模型日志由原有执行器保留。

公共字段比较检查对象名/初值、线程入口及事件的 kind/object/ordering/store value。新增 `scripts/team_pipeline_comparison.py` 直接适配团队实际交付的原生 EventIR/VU，与人工 Oracle 和本次内部基线比较对象类型/来源/字段/分配点、事件、绑定、调用、路径假设、切片、关系及观测条件，不调用内部切片器重建团队 VU。C08 另比较实际团队 C07/C08 VU 的归一化等价性。

`scripts/team_pipeline_artifacts.py` 独立核对实际生成的文件，检查 LLVM/编译诊断、前后端四文件 VU 交付包、值域枚举覆盖、指定查询、litmus 查询条件与寄存器映射、模型命令输入、原始 herd 日志与矩阵缓存，以及架构差异汇总。逐例 `artifact_comparison.json` 保存检查结果和所读取文件的 SHA256。日志缺失为 UNKNOWN，日志与缓存矛盾为 FAIL；两者都阻止该例汇总成一致性 PASS。该检查不重新生成团队产物，也不构成一般 lowering 等价性证明。可单独复核某例：

```bash
python3 scripts/team_pipeline_artifacts.py \
  ../RV-MemoryConsistency-TeamDev/.case-regression-runs/<run>/cases/P02_atomic_fence/pipeline
```

模型目标从团队 `outcome_matrix.json` 的指定查询读取，必须实际 RAN 且观测与独立预期一致，NOT_RUN 不可提升为 PASS。C/P 一致性 PASS 仅覆盖这十一例的有界结构与明确硬件投影；普通访问继续是非 atomic，不代表 C11 无数据竞争或任意优化编译后的程序。B01/B02 当前没有完整前端结构 Oracle，完整程序验证仍 UNKNOWN。

## 状态与退出码

| 字段 | 含义 |
| --- | --- |
| `pipeline.status` | 团队流水线原始结果，包括 PASS、UNSUPPORTED、NOT_RUN、NO_CANDIDATE 等 |
| `pipeline.process_status` | 是否产生有效诊断且退出码符合团队 CLI 协议；它不表示支持该输入 |
| `structure_comparison` | 限定公共字段的比较；没有 EventIR 为 UNKNOWN |
| `artifact_comparison` | 实际中间产物、交付包、litmus 查询条件、原始模型日志和汇总的一致性；缺失文件或证据矛盾不能 PASS |
| `full_structure_comparison` | 团队实际结构、来源、绑定/调用/假设、切片与 VU 的完整适配比较 |
| `query_comparison` | 原始输入指定模型目标与独立预期比较 |
| `equivalence_comparison` | C08/C07 实际团队 VU 的归一化等价检查 |
| `baseline.execution_comparison` | 内部本次检查与其独立预期的比较 |
| `consistency_status` | 声明范围内的跨工具结构与原始硬件目标一致性；未支持或证据不足时为 UNKNOWN |
| `control.comparison` | SB 控制的结构、VU 与真实双架构模型结果比较 |
| `p02_without_fences` | P02 派生删除 fence 对照的源码哈希、调用、结构与真实模型比较 |
| `benchmark_regions` | 原始 B02 的独立函数区域路径抽取及独立文件比较；不参与完整 Benchmark 一致性提升 |

统一退出码：1 表示流程或已实现的比较失败；2 表示覆盖或证据不足；只有流程和完整一致性都 PASS 才返回 0。按协议返回的 UNSUPPORTED 可以令流程检查 PASS，但不会令一致性 PASS。缺少工具、未运行模型与缺少产物均不算通过。

## 证据与复核

`summary.md` 给出逐例结果及拒绝原因；`summary.json` 保留机器结果与 baseline 分层状态。各例的 `logs/` 包含命令、stdout/stderr 和退出码，`pipeline/` 保留团队流水线产物，`artifact_comparison.json` 保存独立文件检查。`control/comparison.json` 保存独立预期和实际结果，`baseline/summary.md` 链接内部本次证据。

`input/inputs.json` 记录 staging 输入哈希；`provenance.json` 记录两个仓库的 HEAD、团队 Python 源码、内部驱动/比较器/基线实现及控制输入的哈希、Python 版本、工具和模型路径及顶层模型哈希。运行结束检查原输入及实现是否仍匹配快照；变化则不能报告流程全部通过。团队执行不导入内部前端或读取内部运行产物；有界 AST 抽取器已作为团队仓库内模块迁入，来源和基线哈希保留在文件头。

改动前首次实测为十三例全部 UNSUPPORTED，定位记录见 [初始诊断](TEAM_PIPELINE_DIAGNOSIS.md)。实现新增模式后的回归中，十一例 C/P 团队流程、完整结构/VU 和原始模型目标比较通过；两个 Benchmark 仍被拒绝，因此总体一致性和统一退出码继续为 UNKNOWN/2。内部架构审查和完整程序结论继续按各层状态记录。

2026-11-10 最终复测证据：[20261110T115518730236/summary.md](../RV-MemoryConsistency-TeamDev/.case-regression-runs/20261110T115518730236/summary.md)。十一例 C/P 共执行132次团队 herd7 查询，另有 SB 控制8次、P02 删除 fence 对照10次；均执行并符合对应比较。团队测试50项、内部测试128项通过。该报告目录由 Git 忽略，复核时需保留整份证据。

2026-11-11 复测证据：[20261111T103343055249/summary.md](../RV-MemoryConsistency-TeamDev/.case-regression-runs/20261111T103343055249/summary.md)。本次补齐中间产物检查后，独立读取并记录 665 个文件的 SHA256，从原始日志复核上述 150 个团队模型结果；十一例 C/P 的产物、完整结构/VU、原始目标与 C08/C07 等价比较均 PASS，两个 Benchmark 仍为 UNSUPPORTED，总体一致性 UNKNOWN、退出码 2。修复前，删除 herd 原始日志仍可使缓存目标比较返回 PASS；新增检查已将真实产物作为汇总的必要条件。新增 11 项测试覆盖产物缺失、缓存与原始日志矛盾、错误模型输入、litmus 条件、交付包、枚举和架构汇总，团队测试 50 项、内部测试 139 项全部通过。此次检查没有修改原始 Case 或人工 Oracle。

## 实现范围与剩余缺口

| 输入 | 当前实现 | 边界 |
| --- | --- | --- |
| C01、C04、C07、P01 | 普通访问、全局字段和对象身份 | 显式 I32 硬件投影，非 C11 数据竞争判定 |
| C02/C05 | 线程实参、局部唯一指针与字段别名 | 静态唯一 scalar int 对象，非一般 may-alias |
| C03 | 分配成功条件、初始化与 join/free 生命周期 | 单一受检查的 scalar malloc |
| C06/C08 | helper、常量局部计算、noise 抽取后切片 | 直线调用，非共享值控制的任意计算 |
| P02 | Fence 抽取、AST/LLVM 配对、切片和 lowering | 原始目标 Never，删除 fence 对照 Sometimes |
| P03 | 三线程、helper、acquire/release 和直接值依赖 | 不支持共享读值的算术或控制流 |
| B01/B02 | 原始源码/include 的可达 AST 特征清单 | main 对象声明即被拒绝；尚无有界路径、数组/位向量和 CAS/RMW 后端 |

团队 [运行说明](../RV-MemoryConsistency-TeamDev/verification_pipeline/README.md)记录两个 EventIR schema、闭包与 lowering 范围。[Benchmark 合同](../RV-MemoryConsistency-TeamDev/verification_pipeline/BENCHMARK_CONTRACT.md)明确循环边界、路径、对象/位宽、线程实例和 CAS 成败语义；其中函数区域路径引擎已实现，完整 Benchmark 路径/VU/ISA 模型尚未完成。`capability_report.json` 是静态过近似，不判断通用头文件中的分支是否可行。

## B02 独立函数区域路径

```bash
python3 scripts/run_benchmark_regions.py
```

该脚本固定 `tests/team_pipeline/benchmarks/b02.regions.json` 的源码/include 哈希，逐字节暂存原始 B02，实际调用团队 `verification_pipeline.bounded`，再由 `scripts/benchmark_region_comparison.py` 独立读取真实路径文件比较。比较器不导入团队实现，也不使用已有手工 SC 锁协议状态机生成预期。B01/B02 八项义务的人工结构需求另存为 `tests/team_pipeline/benchmarks/*.structure.json`；状态为 `DRAFT_UNREVIEWED`，尚不是可执行的完整前端结构 Oracle。

B02 探索范围是两个标签不同、入口相同的 lock/unlock/trylock 区域、两个 await_start 区域、main 的 release_start 区域及 checksum 计算。标签与绑定来自配置，不能称为已经从 main 抽取出两个 worker。每个区域独立执行，不假定跨区域锁状态、启动先后或线程交错。

当前固定预算最多两次 CAS、每个等待点四次读取，生成 40 条路径：27 条返回、13 条循环边界。独立比较按原始循环推导路径形状，检查 indivisible strong CAS、0→1 条件写、失败 `expected` 写回、relaxed 等待、`exp=0` 重置及重试顺序、acquire/release、启动 fetch_add、guard、源码位置、program order 和 U64 checksum。符号读值没有经过路径求解或架构模型，可行性保持 UNKNOWN。

这里的 `EXTRACTED`/`BOUNDARY` 不是完整 Benchmark 的 PASS。尚缺 main/worker、初始化和线程生命周期执行、数组/一般布局、跨线程组合、控制/地址/RMW 闭包、AST/LLVM 配对及 CAS ISA lowering。完整程序一致性 UNKNOWN；脚本即使区域比较 PASS 也退出 2。总接入驱动默认保存此层为 `benchmark_regions/`，并要求区域比较通过；不会据此修改原始十三例的结果。

负向测试包含损坏实际产物，以及在派生暂存头文件中删除 `exp=0` 后显式更新哈希并重新抽取。后者能在来源校验通过后触发独立语义比较失败；原始 Benchmark、原 Oracle 与 vendor 文件未修改。

2026-11-12 复测证据：[20261112T115034100074/summary.md](../RV-MemoryConsistency-TeamDev/.case-regression-runs/20261112T115034100074/summary.md)，其中 [区域证据](../RV-MemoryConsistency-TeamDev/.case-regression-runs/20261112T115034100074/benchmark_regions/summary.md)比较 PASS、路径抽取 BOUNDARY。原有十一例 C/P 的结构、实际产物和双架构目标仍 PASS；完整输入 B01/B02 仍 UNSUPPORTED，总体一致性 UNKNOWN/退出 2。团队测试 77 项、内部测试 153 项通过。

下一阶段先从 B02 main 抽取参数/初始化和两个同入口线程实例，执行 worker 并保留 record/observation 结构；再组合符号 guard、启动 gate、CAS 和线程路径，建立控制/数据/地址/RMW 闭包及可行性判断。完成 CAS 后端原子映射和独立模型比较后，才进入 B01 的数组/布局、批量复制、槽位复用与 U32 环绕。每一步继续要求负向对照和边界耗尽检查。
