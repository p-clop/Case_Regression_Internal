# C03：Heap Escape

- 目的：确认堆对象经线程参数跨线程可达。
- Thread Context：`writer`、`reader`；参数指向同一分配点。
- Shared Object：`malloc` 的 `int` 对象，来源为 heap escape。
- 预期事件：writer `Store(heap_value, 1)`；reader `Load(heap_value)`。
- 预期保留：分配点身份、两次传参与两个访存的关联。
- 预期删除：分配失败检查、join 和 free 的普通控制流；不能丢掉对象身份。
- Verification Unit：两个线程访问同一个初值为 0 的堆对象。
- 路径假设：只构建成功分配后的线程单元；分配失败路径不启动线程，`free` 发生在两个 join 之后。
- 模型结果：结构入口不执行架构比较；新增独立判据与推导见 [architecture.md](architecture.md)，实际比较与正式审查分别记录。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C03_heap_escape/result.json)为准；此说明不预先声明 PASS。该结构记录中的模型项仍为 **UNKNOWN**，架构执行结果见独立入口。

## 正确性要求与判断边界

要求：保留堆分配点、成功路径、初值与对象生命周期前提。结构结果依据独立 `expected.json` 逐字段比较；禁止漏事件、改变对象身份或内存序，以及把潜在通信边当作确定的 reads-from/happens-before。

允许源码位置等解释性元数据变化，但必须满足现有比较器约束；工具不支持或缺少有效产物记 UNKNOWN。此例只做静态结构回归，普通共享访问的 C11 数据竞争限制见[三层验证说明](../../CORRECTNESS.md)，不以原生执行判断允许结果。
