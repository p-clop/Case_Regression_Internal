# P02：Atomic / Fence

人工 Oracle 写在 `expected.json`，不从实际输出反向生成。

- T0：`Store(x,1,relaxed) → Fence(seq_cst) → Load(y,relaxed)`。
- T1：`Store(y,1,relaxed) → Fence(seq_cst) → Load(x,relaxed)`。`x`、`y` 初值为 0。
- 以 `x` 为种子，两个共享对象及全部六个事件均应保留。Fence 没有对象字段，但连接前后保留事件，不得按“无对象”删除。
- 目标结果：T0 读 `y=0` 且 T1 读 `x=0`；x86 和 RISC-V 均预期 `Never`。
- 推导基于明确的 lowering：relaxed 访存投影为普通架构读写；`seq_cst` fence 投影为 x86 `MFENCE` / RISC-V `FENCE RW,RW`。Fence 提供每个线程的 Store→Load 顺序；若两个 Load 都读初值，则“本线程写在本线程读之前、该读在对方写之前”形成顺序环。
- 删除两个 fence 后得到 SB；该变体的目标结果应恢复为两架构均 `Sometimes`，可用作负向敏感性检查。

本例验证上述架构投影及原子内存序的保留，不替代完整 C11 模型检查或任意编译器的映射证明。实际是否通过以报告及 herd7 输出为准。
