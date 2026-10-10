# C03：Heap Escape

- 目的：确认堆对象经线程参数跨线程可达。
- Thread Context：`writer`、`reader`；参数指向同一分配点。
- Shared Object：`malloc` 的 `int` 对象，来源为 heap escape。
- 预期事件：writer `Store(heap_value, 1)`；reader `Load(heap_value)`。
- 预期保留：分配点身份、两次传参与两个访存的关联。
- 预期删除：分配失败检查、join 和 free 的普通控制流；不能丢掉对象身份。
- Verification Unit：两个线程访问同一个初值为 0 的堆对象。
- 路径假设：只构建成功分配后的线程单元；分配失败路径不启动线程，`free` 发生在两个 join 之后。
- 模型结果：UNKNOWN；未定义架构级 litmus Oracle。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C03_heap_escape/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
