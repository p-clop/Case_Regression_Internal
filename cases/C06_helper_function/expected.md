# C06：Helper Function

- 目的：确认被线程入口调用的 helper 访存归属于正确线程。
- Thread Context：`writer → helper_write`、`reader → helper_read`。
- Shared Object：全局 `shared`。
- 预期事件：writer 上下文中的 `Store(shared,1)`；reader 上下文中的 `Load(shared)`。
- 预期保留：入口到 helper 的调用可达关系与两个访存。
- 预期删除：局部返回值的丢弃操作；不得因访存不在入口函数体内而漏掉。
- Verification Unit：两个线程、同一对象、两个事件。
- 模型结果：结构入口不执行架构比较；新增独立判据与推导见 [architecture.md](architecture.md)，实际比较与正式审查分别记录。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C06_helper_function/result.json)为准；此说明不预先声明 PASS。该结构记录中的模型项仍为 **UNKNOWN**，架构执行结果见独立入口。

## 正确性要求与判断边界

要求：将 helper 事件归入对应线程并保留必要调用。结构结果依据独立 `expected.json` 逐字段比较；禁止漏事件、改变对象身份或内存序，以及把潜在通信边当作确定的 reads-from/happens-before。

允许源码位置等解释性元数据变化，但必须满足现有比较器约束；工具不支持或缺少有效产物记 UNKNOWN。此例只做静态结构回归，普通共享访问的 C11 数据竞争限制见[三层验证说明](../../CORRECTNESS.md)，不以原生执行判断允许结果。
