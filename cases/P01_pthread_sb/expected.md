# P01：普通 pthread / Store Buffering

人工 Oracle 写在 `expected.json`，不从实际输出反向生成。

- 线程顺序：`writer`、`reader`，按 `main` 中的 `pthread_create` 顺序编号。
- 完整事件：T0 `Store(x,1) → Load(y) → Store(private_noise,7)`；T1 `Store(y,1) → Load(x)`。初值均为 0。
- 共享对象为 `x`、`y`。以 `x` 为种子，保留两个线程中这两个对象的四个事件及顺序；删除只有 T0 访问且不参与依赖的 `private_noise`。
- 目标结果：T0 读 `y=0` 且 T1 读 `x=0`。普通访存直接投影为架构读写时，x86 TSO 和 RISC-V RVWMO 的预期均为 `Sometimes`：两个线程的写可尚未被对方读观察到。
- **范围限制：此 C 输入有数据竞争，只用于静态抽取、切片和硬件 litmus 投影，不能据此证明 C 程序行为。** 不运行此输入来统计并发结果。

是否通过回归，以工具生成的报告及真实 herd7 输出为准；这里记录的是预先写出的预期。

## 正确性要求与判断边界

要求：保留 SB 四事件并删除 private_noise；两架构目标预期 Sometimes。结构结果依据独立 `expected.json` 逐字段比较；禁止漏事件、改变对象身份或内存序，以及把潜在通信边当作确定的 reads-from/happens-before。

模型允许与禁止行为只针对上述目标条件及明确映射；实际 Sometimes/Never 与比较 PASS/FAIL 分列。正式架构审查未记录时保持 UNKNOWN，详见[三层验证说明](../../CORRECTNESS.md)。
