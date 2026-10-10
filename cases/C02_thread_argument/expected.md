# C02：Thread Argument

- 目的：确认 `main` 的局部对象通过两个 pthread 参数变为 may-shared。
- Thread Context：`writer`、`reader`；两者参数均指向 `main.local`。
- Shared Object：`main.local`，来源为 thread argument；`p` 只是局部别名。
- 预期事件：writer `Store(main.local, 1)`；reader `Load(main.local)`。
- 预期保留：两个访存及参数到对象的指向关系。
- 预期删除：线程句柄、join bookkeeping 和局部读取结果的丢弃操作。
- Verification Unit：两个线程与同一个初值为 0 的对象。
- 模型结果：UNKNOWN；未定义架构级 litmus Oracle。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C02_thread_argument/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
