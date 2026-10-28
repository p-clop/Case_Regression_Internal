# 第一批 Case Matrix

八例已有自动结构回归和独立架构判据。结构入口的模型占位仍为 UNKNOWN；执行 `bash scripts/run_c_architecture.sh` 后查看本地 `results/c_architecture/summary.md`，正式审查与原始 C 正确性保持 UNKNOWN。

本表记录 C01–C08 在本地独立原型中的接入结果，不代表团队核心前端已集成。命令为 `bash scripts/run_internal_regression.sh`；每次实际状态以 [自动结果表](results/internal/summary.md) 为准。

| ID | 共享对象来源 | 程序结构 | 关键 Oracle | 状态 |
| --- | --- | --- | --- | --- |
| C01 | global | 单函数 | 两个访存、同一对象 | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |
| C02 | thread argument | 指针传参 | 局部对象跨线程共享、arg/p 绑定 | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |
| C03 | heap escape | 动态分配 | 分配点、初值、成功路径与绑定 | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |
| C04 | struct field | 字段访问 | data / flag 分开 | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |
| C05 | pointer alias | 指针别名 | p 与 state.flag 同一对象、排除 padding | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |
| C06 | global | helper 调用 | helper 事件归属线程与调用关系 | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |
| C07 | 两个 global | 双对象关系 | 从 flag 扩展到 data | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |
| C08 | 两个 global + noise | 无关代码 | 删除 noise 后目标单元与 C07 等价 | 结构 PASS；架构比较见独立报告，审查 UNKNOWN |

Atomic/Fence 和三线程 release/acquire 的 P01–P03 使用另一组 Oracle，实际结果见 [原型结果表](results/prototype/summary.md)。一般 Mutex/条件变量、复杂别名与控制流仍待扩展。

## 架构查询覆盖

- C01/C02/C03/C05/C06：读 0、读 1 两架构预期 Sometimes；读 2 预期 Never。
- C04/C07/C08：flag=1 且 data=0 预期 x86 Never/RISC-V Sometimes；fenced 对照均 Never，另有正向及未写入值控制。C08 增加保留 noise 的完整事件对照。
- 全部 28 项查询、56 次模型比较；目标、推导与执行边界见[C系列架构说明](C_ARCHITECTURE.md)。
