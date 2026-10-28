# C04_struct_fields：架构投影与独立预期

## 对象与架构映射

来源为两个不同结构体字段；初值与按线程事件序列独立记录在 [architecture.json](architecture.json)，原有 [expected.json](expected.json)继续只判定结构。

显式映射为对齐 32 位普通 Load/Store；对象符号重命名只改变拼写，保持不同对象互不重叠。访存按声明的程序顺序投影，不以 C 编译器实际输出替代。

## 分析前提与语言边界

- 两个 worker 各执行一次；pthread 创建成功；初始化在启动前完成，join 位于投影之外。
- 将保留的普通 int 访问显式映射为对齐、互不重叠的 32 位普通架构访存。
- 按原访存程序顺序保留事件；不引入编译器优化、额外依赖、同步或确定的 reads-from 边。
- 原始 C 普通跨线程冲突访问可能构成数据竞争，仅验证硬件投影，不执行原始 C 推断语言行为。

## 独立查询、预期与推导

| 查询 | 变体 | 目标条件 | x86-TSO 预期 | RVWMO 预期 |
| --- | --- | --- | --- | --- |
| `stale_payload` | `plain` | `T1:E0=1 且 T1:E1=0` | Never | Sometimes |
| `published_payload` | `plain` | `T1:E0=1 且 T1:E1=1` | Sometimes | Sometimes |
| `unwritten_value` | `plain` | `T1:E0=1 且 T1:E1=2` | Never | Never |
| `fenced_stale_payload` | `fenced` | `T1:E0=1 且 T1:E1=0` | Never | Never |

各查询的独立推导如下：

- `stale_payload`：TSO 保留 W(data)->W(flag)与 R(flag)->R(data)，接收 flag=1 后读旧 data 与读值约束冲突；无依赖无屏障的 RVWMO 可放松这两段顺序，存在旧载荷执行。
- `published_payload`：writer 全部完成后 reader 读取为(1,1)可行，reader 先执行又有其他结果；不是 Always。
- `unwritten_value`：data 只由初始化写 0 及 writer 写 1 提供值，没有可供读取的值 2。
- `fenced_stale_payload`：手工对照在 writer 两次写之间加 release fence，在 reader 两次读之间加 acquire fence；RISC-V 对应 fence rw,w 与 fence r,rw，恢复两侧所需顺序，禁止目标。x86 原本保序，映射无需额外指令。

## 消息传递顺序与推导

T0 按序写 `state.data=1`、`state.flag=1`；T1 按序读 flag、读 data。每个位置只有初值 0 与写入值 1，目标 flag=1 定位到 writer 的发布写；事件之间没有值/地址依赖。

plain 是原始保留事件的普通访存投影；fenced 只在架构对照中插入两处屏障，不修改原始源码或结构 Oracle。TSO 两变体均禁止旧载荷；RVWMO 应从 plain 的 Sometimes 变为 fenced 的 Never。

独立保序推导：令 a=W(data,1)、b=W(flag,1)、c=R(flag,1)、d=R(data,0)。TSO 保留 a<b 与 c<d，读 flag=1 定位 b，读 data=0 要求 d 在 a 之前，形成 a<b<c<d<a 的矛盾；无依赖无屏障的 RVWMO 可采用 b,c,d,a 顺序。fenced 对照恢复两段必要保序。

published_payload 防止把所有目标错误地判为 Never；unwritten_value 检查无法解释的读值不会被接受。

## 执行证据与审查状态

运行 `bash scripts/run_c_architecture.sh`，或 `python3 scripts/run_correctness.py`；每次在新目录保存 litmus、寄存器与事件映射、查询单元、stdout/stderr、CAT 及 include 闭包哈希、输入哈希和模型版本。

expected 为上述独立预期，actual 为 herd Observation，comparison 为 PASS/FAIL/UNKNOWN。缺工具、超时或无法解释的结果为 UNKNOWN；不匹配保留 FAIL，不因尚未审查而抹去。

[architecture_reviews.json](architecture_reviews.json)当前为空；正式审查与已审查结论保持 UNKNOWN。实际审查记录须绑定 `subject_sha256`、查询目标、预期和 CAT 闭包，不能用一次输出自动确认。

## 参考规范与模型

[N1570 §5.1.2.4 p25](https://www.open-std.org/jtc1/sc22/WG14/www/docs/n1570.pdf)限定 C 数据竞争边界；[RVWMO说明](https://docs.riscv.org/reference/isa/v20260120/unpriv/mm-eplan.html)解释读值、保序、Fences 及 Table16 的访存映射。

[herdtools7 7.58 x86tso.cat](https://github.com/herd/herdtools7/blob/7.58/herd/libdir/x86tso.cat)与[herd官方说明](https://diy.inria.fr/doc/herd.html)用于固定模型查询与 Observation 含义；本次实际模型快照以执行证据为准。

## 当前缺口

- 尚无正式团队架构 Oracle 审查记录。
- 未验证完整 C 语言数据竞争语义或任意编译器的 C-to-ISA 映射。
- 有限直线硬件投影不代表完整前端集成或任意程序切片正确。

## 验收与后续工作

完成标准是每项硬件查询的目标、推导、模型和证据可独立复核。下一步评审对象映射、目标与模型版本，原始 C 程序正确性继续单独报告。
