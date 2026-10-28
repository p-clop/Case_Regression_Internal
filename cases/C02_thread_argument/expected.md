# C02：Thread Argument

- 目的：确认 `main` 的局部对象通过两个 pthread 参数变为 may-shared。
- Thread Context：`writer`、`reader`；两者参数均指向 `main.local`。
- Shared Object：`main.local`，来源为 thread argument；`p` 只是局部别名。
- 预期事件：writer `Store(main.local, 1)`；reader `Load(main.local)`。
- 预期保留：两个访存及参数到对象的指向关系。
- 预期删除：线程句柄、join bookkeeping 和局部读取结果的丢弃操作。
- Verification Unit：两个线程与同一个初值为 0 的对象。
- 模型结果：结构入口不执行架构比较；新增独立判据与推导见 [architecture.md](architecture.md)，实际比较与正式审查分别记录。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C02_thread_argument/result.json)为准；此说明不预先声明 PASS。该结构记录中的模型项仍为 **UNKNOWN**，架构执行结果见独立入口。

## 正确性要求与判断边界

要求：线程参数传播到同一局部共享对象并保留绑定。结构结果依据独立 `expected.json` 逐字段比较；禁止漏事件、改变对象身份或内存序，以及把潜在通信边当作确定的 reads-from/happens-before。

允许源码位置等解释性元数据变化，但必须满足现有比较器约束；工具不支持或缺少有效产物记 UNKNOWN。此例只做静态结构回归，普通共享访问的 C11 数据竞争限制见[三层验证说明](../../CORRECTNESS.md)，不以原生执行判断允许结果。
