# C08：加入无关代码

- 目的：在 C07 基础上检查切片能删除无关计算和单线程对象。
- Thread Context：`writer → unrelated`、`reader`。
- Shared Object：`data`、`flag`；`noise` 只被 writer 访问，不满足 may-shared 条件。
- 预期事件：与 C07 相同的四个关键访存；另有 `Store(noise,7)`，但它不进入目标单元。
- 预期保留：C07 的四个访存、两对象和必要顺序。
- 预期删除：`unrelated(3)` 的纯局部计算、`Store(noise,7)` 及线程句柄。
- Verification Unit：针对 `seen_flag=1 && seen_data=0`，应与 C07 的目标单元等价。
- 模型结果：结构入口不执行架构比较；新增独立判据与推导见 [architecture.md](architecture.md)，实际比较与正式审查分别记录。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C08_unrelated_code/result.json)为准；此说明不预先声明 PASS。该结构记录中的模型项仍为 **UNKNOWN**，架构执行结果见独立入口。

## 正确性要求与判断边界

要求：删除已抽取的 noise 后目标单元与 C07 等价。结构结果依据独立 `expected.json` 逐字段比较；禁止漏事件、改变对象身份或内存序，以及把潜在通信边当作确定的 reads-from/happens-before。

允许源码位置等解释性元数据变化，但必须满足现有比较器约束；工具不支持或缺少有效产物记 UNKNOWN。此例只做静态结构回归，普通共享访问的 C11 数据竞争限制见[三层验证说明](../../CORRECTNESS.md)，不以原生执行判断允许结果。
