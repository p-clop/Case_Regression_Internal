# Case 与 Benchmark 接入问题定位

本文保留实现改动前的诊断和原始证据。后续已在团队工具中完成 C01–C08、P01–P03 的有界结构与原始硬件目标接入，并补充 P02 删除 fence 对照；当前实现、命令和边界以[团队流水线集成](TEAM_PIPELINE.md)为准。B01/B02 仍未完成完整前端与路径模型。

## 本次实测结论

2026-11-10 使用已有 `scripts/run_team_pipeline.py`，将 C01–C08、P01–P03、B01/B02 原始输入复制并校验后，实际送入团队 `verification_pipeline`。十三例全部在前端返回 `UNSUPPORTED`，尚未进入 VU 生成和模型验证。主要阻塞是流水线的语义能力范围，而非本次 Clang/herd7 环境故障。

本次证据位于团队仓库 [20261110T112705733957/summary.md](../RV-MemoryConsistency-TeamDev/.case-regression-runs/20261110T112705733957/summary.md)，该目录为本地忽略产物，需要随本报告保留才能复核。

| 检查 | 本次结果 | 含义 |
| --- | --- | --- |
| 十三例原始输入调用 | 13/13 `UNSUPPORTED` | 调用成功，输入语义尚未支持 |
| 独立 relaxed atomic SB 控制 | PASS | 2 线程、2 对象、4 事件、1 VU；四组读值 × 两架构共 8 次真实 herd7 查询符合预期 |
| 内部本次执行比较 | 13/13 PASS | 内部声明的结构、原型、原生和投影检查符合各自预期 |
| Benchmark 内部基线 | 34 次原生运行、12 次模型调用，比较 PASS | 原生行为和人工事件投影的证据，不代表团队已自动抽取完整程序 |
| 原始输入跨工具完整一致性 | UNKNOWN | 缺少团队产物，也尚未完成完整 Oracle 适配 |
| 输入与团队代码版本检查 | PASS | 运行期间快照匹配 |
| 接入驱动器已有单元测试 | 8/8 PASS | 覆盖退出码、缺失证据、结构/VU/模型差异与 staging 检查 |

集成命令退出码为 2，含义是覆盖或证据不足。报告中的 `process_status=PASS` 只表示调用与诊断符合协议，不能解读为十三例已接入。

## 逐例实际拒绝点

下表记录首次触发的检查；排除该检查后仍可能遇到其他未支持语义。

| 输入 | 实际拒绝信息 | 对应代码 | 需要补齐的能力 |
| --- | --- | --- | --- |
| C01_global | Only local scalar assignment of a direct atomic Load is supported | `frontend/extractor.py:173` | 普通全局访问的结构抽取及单独声明的硬件投影范围 |
| C02_thread_argument | Only default attributes and null pthread arguments are supported | `frontend/extractor.py:87` | 线程实参与局部对象绑定、指针解引用 |
| C03_heap_escape | Control flow in pthread lifecycle is not modeled | `frontend/extractor.py:62` | 分配成功路径、初始化、堆对象身份及 join/free 生命周期 |
| C04_struct_fields | Only local scalar assignment of a direct atomic Load is supported | `frontend/extractor.py:173` | 普通字段访问、字段对象身份 |
| C05_pointer_alias | Only scalar local int observation/constant declarations are supported | `frontend/extractor.py:160` | 静态唯一指针别名、字段解析 |
| C06_helper_function | Unmodeled worker statement CallExpr in writer | `frontend/extractor.py:188` | 跨函数抽取、调用关系和事件所属线程 |
| C07_two_objects | Only local scalar assignment of a direct atomic Load is supported | `frontend/extractor.py:173` | 普通双对象访问、顺序与 VU 比较 |
| C08_unrelated_code | Unmodeled local initializer/dependency | `frontend/extractor.py:167` | 局部计算/helper、普通访问，以及 noise 抽取后删除 |
| P01_pthread_sb | Only local scalar assignment of a direct atomic Load is supported | `frontend/extractor.py:173` | 普通访问、private_noise 切片 |
| P02_atomic_fence | Unmodeled worker statement CallExpr in writer | `frontend/extractor.py:188` | `atomic_thread_fence` 抽取、保留和双架构 lowering |
| P03_release_acquire_relay | Exactly two distinct pthread entries/handles and two joins are required | `frontend/extractor.py:103` | 三线程、helper、acquire/release 和 Load→Store 值依赖 |
| B01_spsc_ring | Control flow in pthread lifecycle is not modeled | `frontend/extractor.py:62` | 另需结构体、数组、间接寻址、循环分支、模运算、运行时计算和同步 |
| B02_spinlock | Control flow in pthread lifecycle is not modeled | `frontend/extractor.py:62` | 另需同一 worker 多实例、循环创建/等待/重试、CAS 成败路径及锁保护关系 |

表中路径均相对于团队仓库 `verification_pipeline/`。源码入口见 [extractor.py](../RV-MemoryConsistency-TeamDev/verification_pipeline/frontend/extractor.py)。C01 的报错提到 atomic Load，但实际首先遇到的是 `shared = 1`；它来自统一赋值语句检查，不能据此判断源码本身语法错误。

## 接口与后端还存在独立阻塞

### 外部路径必须先进入团队 worktree

直接在团队仓库执行以下命令，实际返回 `INVALID_INPUT`、退出码 1：

```bash
python3 -m verification_pipeline \
  --source ../Case_Regression_Internal/cases/P02_atomic_fence/case.c \
  --out .case-regression-runs/external-path-probe-20261110 \
  --backend local
```

原因为 `Path must be within current worktree`，检查位于 [common.py](../RV-MemoryConsistency-TeamDev/verification_pipeline/frontend/common.py) 的 `worktree_path()`。已有接入驱动器通过复制输入、保留 Benchmark 相对 include 关系及校验哈希解决；本次十三例均已越过此限制。

### 内部 EventIR 不能直接替换团队 EventIR

内部使用 `version=prototype-1`、`objects`、`threads[].events`、`edges`，团队要求 `schema_version=backend-capability-event-ir-v1`、`shared_objects`、`thread_contexts`、扁平 `events`、`relations.program_order` 和独立 SourceMap。直接以本次 C01 内部 EventIR 调用团队验证器，实际返回 `INVALID_INPUT: Unsupported Event IR schema_version`。

即使完成字段转换，语义检查仍会拒绝普通对象、Fence、Acquire、三线程和非常量 Store。本次从通过控制例构造的单项接口探针分别确认了这些拒绝，结果见 [contract_probes.json](../RV-MemoryConsistency-TeamDev/.case-regression-runs/20261110T112705733957/contract_probes.json)。这些是人工构造的接口检查，不是原始输入准入成功证据。

### 只放宽抽取器不足以完成接入

- [frontend/common.py](../RV-MemoryConsistency-TeamDev/verification_pipeline/frontend/common.py) 的 `validate_graph()` 再次限定两线程、I32、relaxed atomic Load/Store、常量 Store 和仅 program order 关系；对象名也必须符合 litmus 标识符规则，`state.flag`、`main.local` 等身份需要显式映射。
- [backend/bundle.py](../RV-MemoryConsistency-TeamDev/verification_pipeline/backend/bundle.py) 的 `load_vu_bundle()` 独立重复两线程、访问种类、宽度和内存序限制。
- [frontend/discovery.py](../RV-MemoryConsistency-TeamDev/verification_pipeline/frontend/discovery.py) 的交互分组按两个线程的相对顺序计算 reversal；不能仅删除线程数量检查就支持 P03。
- [frontend/closure.py](../RV-MemoryConsistency-TeamDev/verification_pipeline/frontend/closure.py) 仅保留目标对象的访问；扩展到 Fence、值依赖或控制依赖时，需要新的闭包规则。
- [backend/lowering.py](../RV-MemoryConsistency-TeamDev/verification_pipeline/backend/lowering.py) 只生成 MOV 或 lw/sw，不具备 Fence、acquire/release、CAS/RMW 和路径语义的生成分支。

因此，把普通访问标成 `atomic=True`、删除 fence 或省略 CAS 重试会改变待验证语义，不能作为原始输入接入完成的依据。普通 C 访问的结构抽取、显式硬件投影与 C11 程序语义也需要分别记录。

## 建议的实施顺序

以下是后续方案，本轮未修改团队实现或原始 Case/Oracle。

1. **先以 P02 完成一条新增语义的完整链路。** 该输入已符合两线程、全局 atomic I32 和常量写入范围，主要新增 Fence。同步扩展 AST/LLVM 配对、EventIR 合同、闭包、后端校验与 lowering；验收原始 P02 的目标在两架构均为 Never，并保留已有删除 fence 后恢复 Sometimes 的对照。
2. **再接入 C01/C07/P01 的普通访问结构抽取。** 明确普通访问的语义模式和结论范围，建立完整产物比较后再增量覆盖字段、参数、别名、helper 和堆对象。内部 `prototype/frontend.py` 与 `prototype/graph.py` 可提供已有实现参考，但不能把内部基线当作团队执行结果。
3. **单独设计 P03 的多线程与依赖合同。** 需要调整交互分组和闭包，保留 Load→Store 依赖及 acquire/release，不只是增加线程上限。
4. **最后开展完整 Benchmark 前端接入。** 先约定循环界限、路径表示、数组/对象/位宽、同一入口的线程实例及 CAS 原子性，再实现抽取与模型映射。现有原生与人工投影继续作为独立证据。

现有接入脚本只比较公共结构字段，源码中完整一致性仍固定为 UNKNOWN；B01/B02 尚无前端结构 Oracle。即使将来原始输入能运行，也需补齐来源、别名、调用、路径、切片、完整 VU 和模型目标比较，才能关闭一致性缺口。

## 复现

```bash
cd /home/zhovy/work/Case_Regression_Internal
source ../.tools/case-regression-env.sh
python3 scripts/run_team_pipeline.py --backend local
python3 -m unittest discover -s tests -p test_team_pipeline.py -v
```

每次集成运行生成新的证据目录。完整原始 stdout/stderr、执行命令、源码哈希、工具和模型路径、各例 manifest 及本次内部基线均保留在对应目录。
