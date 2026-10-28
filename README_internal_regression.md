# C01–C08 自动结构回归

八个原始 `case.c` 保持不变，现已接入 Clang 前端、共享对象分析、切片与 Verification Unit 的自动比较。
每个 Case 的 `expected.json` 都按源码和原有 `expected.md` 人工编写，格式版本为 2；不从工具输出生成 Oracle。

## 执行与结果

```bash
cd /home/zhovy/work/Case_Regression_Internal
bash scripts/run_internal_regression.sh
```

默认使用 `tests/internal_manifest.json` 中的八个 Case，缺失文件会记录 UNKNOWN，不会因目录扫描漏掉而报告全通过。
可显式传入 Case 目录；C08 需要与 C07 一起运行，才能完成本次运行中的等价检查。

```bash
bash scripts/run_internal_regression.sh cases/C07_two_objects cases/C08_unrelated_code --out results/pair
```

工具入口为 `python3 -m prototype.internal`，支持 `--clang`、`--out`、`--timeout` 和 `--artifacts`。
Clang 安装沿用 [原型环境说明](README_prototype.md)。这个结构回归入口不需要 herd7。

结果文件：

- [summary.md](results/internal/summary.md)：便于阅读的结果表。
- [summary.csv](results/internal/summary.csv)：可导入表格软件，UTF-8 BOM 编码。
- [summary.json](results/internal/summary.json)：完整机器可读汇总，含本次 Case 清单、工具版本和分项状态。
- 每例的 `comparison.json`：按字段列出 `path`、`expected`、`actual`。
- 每例的 `result.json`：本次运行状态、来源哈希、实际产物哈希、错误原因及额外等价检查。

结构结果为 PASS/0、FAIL/1、UNKNOWN/2。FAIL 表示与独立 Oracle 不匹配；UNKNOWN 表示缺少工具、输入能力不支持、Oracle 无效、输出缺失或来源校验未通过。
本结构入口的 `verification.x86.status` 和 `verification.riscv.status` 保持 UNKNOWN，原因为 `architecture_checked_by_separate_runner`。新增架构判据位于各例 `architecture.json`，执行 `bash scripts/run_c_architecture.sh`；模型比较与正式审查分别记录，见 [C系列架构说明](C_ARCHITECTURE.md)。
这里的结构 PASS 不代表模型验证通过，也不改变原始普通 C 共享变量可能存在数据竞争的事实。

## 比较内容

| 分项 | 检查内容 |
| --- | --- |
| shared_objects | 全部已访问对象与 may-shared 集合、类型、初值、来源、字段路径和堆分配点；禁止 C05 的未访问 padding 进入对象集 |
| events | 线程入口与顺序、事件数量/身份/类型/对象/内存序/写值、helper 所属函数，以及有效源码位置 |
| slice | seed、应保留和应删除的事件 ID、删除的对象；保留/删除集合必须完整划分抽取事件 |
| verification_unit | 保留对象、每线程事件序列、po/值依赖/潜在通信边、观测条件、参数/别名绑定和必要 helper 调用 |
| bindings | 原始 EventIR 的线程实参、局部指针绑定、helper 调用和条件路径假设 |

Verification Unit 中每个事件和对象还必须与 EventIR 的原始记录一致，不能保留了 ID 却改变其含义。
C03 的成功分配假设必须出现在 EventIR，并完整传入 Verification Unit。
C08 另有 `equivalence` 检查：归一化事件 ID 和源码元数据后，目标单元必须与 C07 相同。
这项检查保留对象身份、初值、事件顺序、内存序、依赖和观测条件，不是只比较事件数量。

`pthread` 句柄、join bookkeeping、纯局部计算不会产生内存事件；这是抽取层的抽象。
`noise` 则先产生事件，再由切片删除。两类情况在 Oracle 中分别检查，不能把“没有抽取”都说成“切片成功”。

## EventIR 输出格式

完整例子：[C02 eventir.json](results/internal/C02_thread_argument/eventir.json)、[C03 eventir.json](results/internal/C03_heap_escape/eventir.json)。
顶层格式：

```text
version: "prototype-1"
source: {path: string}
objects: MemoryObject[]
threads: [{id: "T0", index: 0, entry: "writer", events: Event[]}]
bindings: Binding[]
calls: [{thread, caller, callee}]
assumptions: [{kind, allocation_site, source_location}]
diagnostics: string[]
```

`MemoryObject` 必含 `id`、`type`、`initial`、`origin`、`source_location`。
其中 `origin` 为 `global`、`thread_argument` 或 `heap_escape`；`type` 在这八例中均为 `int`。
字段对象另含 `base_object` 与 `field_path`，例如 `state.flag`、`state`、`["flag"]`。
堆对象另含 `allocation_site: {id: "main:malloc:0", function: "main", source_location}`。
对象只在实际产生内存事件时进入 `objects`，不会把局部指针变量本身当成共享对象。

```json
{
  "id": "T0:E0",
  "kind": "Store",
  "object": "main.local",
  "ordering": "plain",
  "value": 1,
  "function": "writer",
  "source_location": {"line": 5, "column": 5}
}
```

事件 ID 在 Case 内唯一，线程中的数组顺序代表源码抽取顺序。Load 有 `target`，Store 有 `value`；写值可以是整数或 `{"event":"T0:E0"}`。
`source_location` 为 Clang 的一基行号/字节列号。
绑定格式：

```json
{
  "kind": "pointer_alias",
  "thread": "T0",
  "function": "writer",
  "name": "p",
  "object": "main.local"
}
```

线程入口实参使用同样格式，`kind` 为 `thread_argument`，`name` 为形参名 `arg`。
这里表示一个静态唯一的已解析对象，不表示支持一般 may-alias 分析。

## 切片和 Verification Unit 格式

完整例子：[C08 slice.json](results/internal/C08_unrelated_code/slice.json)、[C08 unit.json](results/internal/C08_unrelated_code/unit.json)。
`slice.json` 与 `unit.json.slice` 必须完全相同：

```json
{
  "strategy": "conservative_shared_object_thread_closure",
  "retained_events": ["T0:E1", "T0:E2", "T1:E0", "T1:E1"],
  "removed_events": ["T0:E0"],
  "removed_objects": ["noise"]
}
```

`unit.json` 包含 `version`、`source`、`shared_objects`、`seed_objects`、`objects`、`threads`、`edges`、`bindings`、`calls`、`assumptions`、`outcome`、`slice`、`scope`、`limitations`。
对象和线程事件使用 EventIR 的同一结构；只保留目标单元所需对象、事件、指针绑定与 helper 调用。
因此 C06 的 helper 调用留在单元里，而 C08 的纯局部 `unrelated` 调用只保留在原始 EventIR 中。

边格式为 `{"kind":"po","from":"T0:E1","to":"T0:E2"}`，也可为 `data` 或 `communication_candidate`。
潜在通信边不是已确定的 reads-from 或 happens-before 关系。
观测格式为 `{"thread":1,"event":"T1:E0","value":1}`；没有观测 Oracle 的 Case 使用空数组，仍可做结构比较。

## 接入另一套前端输出

每个 Case 提供同名子目录中的 `eventir.json`、`slice.json`、`unit.json` 和 `manifest.json`，即可复用现有比较器。
`manifest.json` 的格式为：

```text
version: "internal-artifacts-1"
source_sha256: 当前 case.c 的 SHA256
sha256:
  eventir.json: 对应文件 SHA256
  slice.json: 对应文件 SHA256
  unit.json: 对应文件 SHA256
```

```bash
python3 -m prototype.internal --artifacts /path/to/exported-cases --out results/imported
```

导入模式不运行 Clang 或重建切片，直接比较所提供的实际产物；验证源文件与产物哈希后才开始比较。
输出缺失、过期或校验不一致会标 UNKNOWN。该校验用于防止误用旧结果，不是对外部工具可信性的认证。
若团队现有格式不同，应先编写转换器；不要修改人工 Oracle 以迎合工具输出。

## 支持范围与验证

新增支持局限于这批样例体现的语义：直接 int 对象地址、线程参数传播、静态唯一的局部 int 指针别名、全局扁平 int 结构体字段，以及一个已检查分配失败、在线程启动前初始化的 malloc 对象。
C03 的失败分配路径不会创建线程，当前单元明确以分配成功路径为条件；free 只能在线程全部 join 之后。
分支选择别名、指针算术、多个分配点、嵌套结构、数组、任意控制流仍明确拒绝。

```bash
source ../.tools/case-regression-env.sh
python3 -m unittest discover -s tests -v
bash scripts/run_prototype.sh
```

测试包括实际八例抽取、故意删除/增添/重排事件、改动对象来源与初值、丢失别名/条件、错误保留 noise、损坏 po、导入过期输出等情况。
P01–P03 的既有真实 herd7 验证和同步删除对照继续运行。
