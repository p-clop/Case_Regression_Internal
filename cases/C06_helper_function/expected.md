# C06：Helper Function

- 目的：确认被线程入口调用的 helper 访存归属于正确线程。
- Thread Context：`writer → helper_write`、`reader → helper_read`。
- Shared Object：全局 `shared`。
- 预期事件：writer 上下文中的 `Store(shared,1)`；reader 上下文中的 `Load(shared)`。
- 预期保留：入口到 helper 的调用可达关系与两个访存。
- 预期删除：局部返回值的丢弃操作；不得因访存不在入口函数体内而漏掉。
- Verification Unit：两个线程、同一对象、两个事件。
- 模型结果：UNKNOWN；未定义架构级 litmus Oracle。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C06_helper_function/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
