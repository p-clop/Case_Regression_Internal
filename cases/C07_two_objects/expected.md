# C07：两个共享对象

- 目的：确认以 `flag` 为 seed 时，切片会扩展到相关的 `data`。
- Thread Context：`writer`、`reader`。
- Shared Object：全局 `data`、`flag`。
- 预期事件：writer `Store(data,1) → Store(flag,1)`；reader `Load(flag) → Load(data)`。
- 预期保留：四个访存、两个对象及线程内顺序。
- 预期删除：线程句柄和局部结果的丢弃操作。
- Verification Unit：针对 `seen_flag=1 && seen_data=0`，保留两个对象，不能只留 `flag`。
- 模型结果：结构入口不执行架构比较；新增独立判据与推导见 [architecture.md](architecture.md)，实际比较与正式审查分别记录。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C07_two_objects/result.json)为准；此说明不预先声明 PASS。该结构记录中的模型项仍为 **UNKNOWN**，架构执行结果见独立入口。

## 正确性要求与判断边界

要求：由 flag 扩展保留 data 及双对象顺序和潜在通信关系。结构结果依据独立 `expected.json` 逐字段比较；禁止漏事件、改变对象身份或内存序，以及把潜在通信边当作确定的 reads-from/happens-before。

允许源码位置等解释性元数据变化，但必须满足现有比较器约束；工具不支持或缺少有效产物记 UNKNOWN。此例只做静态结构回归，普通共享访问的 C11 数据竞争限制见[三层验证说明](../../CORRECTNESS.md)，不以原生执行判断允许结果。
