# C01：Global Shared Object

- 目的：确认全局对象可被两个线程归属和识别。
- Thread Context：`writer`、`reader`。
- Shared Object：`shared`，来源为 global。
- 预期事件：writer `Store(shared, 1)`；reader `Load(shared)`。
- 预期保留：两个访存事件及其线程归属。
- 预期删除：`main` 中的线程句柄、join bookkeeping；`(void)` 局部使用不形成共享事件。
- Verification Unit：两个线程、`shared=0`、上述 Store/Load。
- 模型结果：UNKNOWN；未定义架构级 litmus Oracle。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C01_global/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
