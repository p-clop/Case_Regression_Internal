# 第一批 Case Matrix

当前八例已通过独立原型的实际自动结构回归，模型状态全部为 `UNKNOWN`（没有经过审查的架构模型 Oracle）。

本表记录 C01–C08 在本地独立原型中的接入结果，不代表团队核心前端已集成。命令为 `bash scripts/run_internal_regression.sh`；每次实际状态以 [自动结果表](results/internal/summary.md) 为准。

| ID | 共享对象来源 | 程序结构 | 关键 Oracle | 状态 |
| --- | --- | --- | --- | --- |
| C01 | global | 单函数 | 两个访存、同一对象 | 结构 PASS；模型 UNKNOWN |
| C02 | thread argument | 指针传参 | 局部对象跨线程共享、arg/p 绑定 | 结构 PASS；模型 UNKNOWN |
| C03 | heap escape | 动态分配 | 分配点、初值、成功路径与绑定 | 结构 PASS；模型 UNKNOWN |
| C04 | struct field | 字段访问 | data / flag 分开 | 结构 PASS；模型 UNKNOWN |
| C05 | pointer alias | 指针别名 | p 与 state.flag 同一对象、排除 padding | 结构 PASS；模型 UNKNOWN |
| C06 | global | helper 调用 | helper 事件归属线程与调用关系 | 结构 PASS；模型 UNKNOWN |
| C07 | 两个 global | 双对象关系 | 从 flag 扩展到 data | 结构 PASS；模型 UNKNOWN |
| C08 | 两个 global + noise | 无关代码 | 删除 noise 后目标单元与 C07 等价 | 结构 PASS；模型 UNKNOWN |

Atomic/Fence 和三线程 release/acquire 的 P01–P03 使用另一组 Oracle，实际结果见 [原型结果表](results/prototype/summary.md)。一般 Mutex/条件变量、复杂别名与控制流仍待扩展。
