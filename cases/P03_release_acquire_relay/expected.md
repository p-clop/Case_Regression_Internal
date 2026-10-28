# P03：三线程 Release / Acquire 传递与 Helper

人工 Oracle 写在 `expected.json`，不从实际输出反向生成。

- 三个线程及调用路径：T0 `writer → publish_data`；T1 `relay → relay_once`；T2 `reader → observe_data`。
- T0：`Store(data,1,relaxed) → Store(flag,1,release)`。
- T1：`seen = Load(flag,acquire) → Store(relay_flag,seen,release)`。Store 必须保留来自 `T1:E0` 的值依赖，不得替换为常量 1。
- T2：`Load(relay_flag,acquire) → Load(data,relaxed)`。三个原子对象初值均为 0。
- 以 `data` 为种子，保留三个线程、三个共享对象、六个事件，以及 helper 调用上下文、线程内顺序和 T1 的值依赖。
- 目标结果：T1 读 `flag=1`，T2 读 `relay_flag=1`，但 T2 读 `data=0`；x86 和 RISC-V 均预期 `Never`。目标结果中的两次成功 acquire 接收对应 release 发布的值，使 T0 的数据发布经过 T1 传到 T2；所选架构 lowering 必须保留这个传递顺序。
- 明确 lowering：x86 TSO 用普通读写实现此例的 acquire/release；RISC-V 在 release Store 前放 `FENCE RW,W`，在 acquire Load 后放 `FENCE R,RW`，并保留 relay 值依赖。

这是无循环、无条件分支的三线程同步传递样例，不表示已支持 mutex、condition variable、屏障 API 或任意复杂同步。验证对象是所选架构投影；完整 C11 验证和编译器映射正确性不在本原型范围。实际是否通过以报告及 herd7 输出为准。

## 正确性要求与判断边界

要求：保留三线程同步、helper 与读到写值依赖；传递成功却读旧 data 的目标预期 Never。结构结果依据独立 `expected.json` 逐字段比较；禁止漏事件、改变对象身份或内存序，以及把潜在通信边当作确定的 reads-from/happens-before。

模型允许与禁止行为只针对上述目标条件及明确映射；实际 Sometimes/Never 与比较 PASS/FAIL 分列。正式架构审查未记录时保持 UNKNOWN，详见[三层验证说明](../../CORRECTNESS.md)。
