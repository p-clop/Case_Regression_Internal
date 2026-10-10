# C04：Struct Field

- 目的：确认字段敏感的对象身份。
- Thread Context：`writer`、`reader`。
- Shared Object：`state.data` 与 `state.flag`，两个不同 Field Path。
- 预期事件：writer `Store(data,1) → Store(flag,1)`；reader `Load(flag) → Load(data)`。
- 预期保留：四个事件、两个字段身份及各线程程序顺序。
- 预期删除：局部 `seen_*` 的丢弃操作；不得把两个字段合并成单一无字段对象。
- Verification Unit：两个对象、两个线程、四个事件；目标绑定为 `flag=1 && data=0`，只验证结构，不判定该结果的可达性。
- 模型结果：UNKNOWN；需要独立生成并审查 litmus。
- 自动结构 Oracle：[`expected.json`](expected.json)，独立依据源码和上述人工预期编写；覆盖共享对象、完整事件、切片保留/删除与 Verification Unit。
- 实际结构结果：运行自动回归后，以[结果记录](../../results/internal/C04_struct_fields/result.json)为准；此说明不预先声明 PASS。模型状态仍为 **UNKNOWN**。
