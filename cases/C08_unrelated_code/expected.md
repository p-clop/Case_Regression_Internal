# C08：加入无关代码

- 目的：在 C07 基础上检查切片能删除无关计算和单线程对象。
- Thread Context：`writer → unrelated`、`reader`。
- Shared Object：`data`、`flag`；`noise` 只被 writer 访问，不满足 may-shared 条件。
- 预期事件：与 C07 相同的四个关键访存；另有 `Store(noise,7)`，但它不进入目标单元。
- 预期保留：C07 的四个访存、两对象和必要顺序。
- 预期删除：`unrelated(3)` 的纯局部计算、`Store(noise,7)` 及线程句柄。
- Verification Unit：针对 `seen_flag=1 && seen_data=0`，应与 C07 的目标单元等价。
- 模型结果：UNKNOWN；本回归比较静态结构及与 C07 的目标单元等价性，不判定硬件结果的可达性。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C08_unrelated_code/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
