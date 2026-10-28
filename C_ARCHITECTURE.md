# C01–C08 独立架构判据与验证

## 结构 Oracle 与独立架构判据

C01–C08 的 `expected.json` 继续判定结构，其 `expected_observations` 占位不用于架构执行。每例新增 `architecture.json`、`architecture.md` 及 `architecture_reviews.json`，分别保存机器预期、独立推导和真实审查记录。

`architecture.json` 由源码及明确映射人工定义，绑定 case.c 和 `expected.json` 哈希，不从前端或 herd 输出反填。实际单元与独立对象、初值、线程事件顺序不匹配时拒绝继续，不能为了 PASS 静默改写事件。

## 查询类型与预期

- C01、C02、C03、C05、C06：单对象初值 0、一次写 1。读 0 和读 1 在 x86-TSO/RVWMO 均预期 Sometimes，读未写入的 2 均预期 Never；验证身份、初值和投影，不宣称存在架构风险差分。
- C04、C07、C08：writer 先写 data=1 后写 flag=1，reader 先读 flag 后读 data。普通投影目标 flag=1 且 data=0 预期 x86 Never、RISC-V Sometimes；另查(1,1)可达及未写入值不可达。
- 三例 MP 增加手工 fenced 对照：writer 两次写之间插入 release fence，reader 两次读之间插入 acquire fence，目标两架构均预期 Never。只改架构对照，不改原始源码或结构预期。
- C08 再保留 noise 写入作 full_noise 对照。全部八例共 28 项查询、56 次架构模型比较，实际执行数以报告为准。

## 地址、位宽与语言边界

- 对象显式映射为对齐且不重叠的 32 位位置；main.local、state.flag 等仅重命名为安全符号，禁止两个对象撞名。helper、线程参数、别名和分配成功路径先由结构 Oracle 核对，再投影其访存。
- 初始化位于 worker 启动前，两个 worker 各运行一次，pthread 创建成功，join 位于投影外；C03 只分析 malloc 成功路径及 join 后 free 的生命周期前提。
- 这些普通 C 并发访问可能存在语言层数据竞争；投影不是实际编译器输出，不证明原始 C 正确，也不证明任意布局、混合位宽访问、无限控制流或核心前端已集成。

## 执行与复现

执行`bash scripts/run_c_architecture.sh`，自动运行当前结构检查，再将 56 个声明查询送入 herd。依赖沿用既有工具，可先`source ../.tools/case-regression-env.sh`，也可用--clang、--herd7、--x86-model、--riscv-model 指定。

已有当前结构结果时使用`--internal /path/to/internal`；需核对来源及产物哈希。`--case C07_two_objects`可选单例；单选 C08 时会为结构等价检查补跑 C07。

默认在 `results/c_architecture/` 中新建独立目录，并更新本地 `summary.md`、`latest.json` 入口；该目录及入口均由 Git 忽略，运行后查看 `results/c_architecture/summary.md`。`--out` 只接受空目录，不覆盖旧证据。PASS/0 为已声明比较符合预期，FAIL/1 为可复现不匹配，UNKNOWN/2 为缺少可靠证据。

`python3 scripts/run_correctness.py`先运行结构、原型和 Benchmark，再复用本次结构结果运行 C 架构查询，统一报告仍为 13 个 Case。只汇总旧证据时可给既有--collect 命令追加`--architecture /path/to/architecture`；省略表示没有提供该层证据，不能说已执行架构检查。

## 查询证据与状态

- 每项输出投影单元、x86/RISC-V litmus、事件到寄存器映射、stdout/stderr、返回码、命令和实际 Observation。`result.json` 绑定源码、结构 Oracle、架构材料、执行代码与 CAT include 闭包哈希。
- `comparison_status` 为本次预期比较；`review_status` 为正式审查；`conclusion_status` 为已审查预期下的结论；c_program_correctness 始终单独记录。比较 PASS 不自动确认审查，不匹配 FAIL 也不因审查 UNKNOWN 而被抹去。
- 汇总时检查输入和产物版本及 CAT 闭包；缺失、篡改、过期或缺查询不能复用为 PASS。版本哈希用于防止误用旧证据，不认证工具或评审身份。

## 架构 Oracle 审查

`architecture_reviews.json` 使用 c-architecture-reviews-1，records 当前为空；真实发生审查后再登记。target 示例为 stale_payload.riscv，每条还需 decision=CONFIRMED、review_id、reviewer、带时区 reviewed_at 和 rationale。

`subject_sha256` 取本次 provenance.review_subject_sha256，expected 与 model_files 取对应查询；源码、材料、执行代码或模型变化会使旧记录失效。审查文件从 subject 排除，添加记录不会让自身立即失效，但需要重新执行或核对当前版本以生成新报告。

rationale 应核对事件来源、目标、保序与读值推导、模型版本和适用边界。自动运行或编写人自己的结果不填成团队正式评审。

## 验收与后续工作

完成标准是八例各有独立目标与依据，正反对照有明确预期，模型输出和版本证据可复核。下一步开展逐项架构审查，原始 C 程序正确性及完整工具链集成继续按独立范围推进。
