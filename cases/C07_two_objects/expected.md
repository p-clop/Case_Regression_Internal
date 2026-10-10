# C07：两个共享对象

- 目的：确认以 `flag` 为 seed 时，切片会扩展到相关的 `data`。
- Thread Context：`writer`、`reader`。
- Shared Object：全局 `data`、`flag`。
- 预期事件：writer `Store(data,1) → Store(flag,1)`；reader `Load(flag) → Load(data)`。
- 预期保留：四个访存、两个对象及线程内顺序。
- 预期删除：线程句柄和局部结果的丢弃操作。
- Verification Unit：针对 `seen_flag=1 && seen_data=0`，保留两个对象，不能只留 `flag`。
- 模型结果：UNKNOWN；这是静态抽取/切片 Oracle，非原始 C 程序的模型结论。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C07_two_objects/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
