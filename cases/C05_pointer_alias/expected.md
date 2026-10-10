# C05：Pointer Alias

- 目的：确认 `p` 与 `state.flag` 指向同一内存对象。
- Thread Context：`writer`、`reader`。
- Shared Object：`state.flag`；`state.padding` 未访问，不应进入候选。
- 预期事件：writer 经 `p` 执行 `Store(state.flag,1)`；reader `Load(state.flag)`。
- 预期保留：别名关系和两个访存。
- 预期删除：未访问的 `padding`、局部指针变量本身的非共享操作。
- Verification Unit：两个线程访问同一个 `state.flag`。
- 模型结果：UNKNOWN；未定义架构级 litmus Oracle。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C05_pointer_alias/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
