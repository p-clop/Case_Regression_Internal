# C05_pointer_alias：架构投影与独立预期

## 对象与架构映射

来源为别名指向的同一结构体字段；初值与按线程事件序列独立记录在 [architecture.json](architecture.json)，原有 [expected.json](expected.json)继续只判定结构。

显式映射为对齐 32 位普通 Load/Store；对象符号重命名只改变拼写，保持不同对象互不重叠。访存按声明的程序顺序投影，不以 C 编译器实际输出替代。

## 分析前提与语言边界

- 两个 worker 各执行一次；pthread 创建成功；初始化在启动前完成，join 位于投影之外。
- 将保留的普通 int 访问显式映射为对齐、互不重叠的 32 位普通架构访存。
- 按原访存程序顺序保留事件；不引入编译器优化、额外依赖、同步或确定的 reads-from 边。
- 原始 C 普通跨线程冲突访问可能构成数据竞争，仅验证硬件投影，不执行原始 C 推断语言行为。

## 独立查询、预期与推导

| 查询 | 变体 | 目标条件 | x86-TSO 预期 | RVWMO 预期 |
| --- | --- | --- | --- | --- |
| `read_initial` | `plain` | `T1:E0=0` | Sometimes | Sometimes |
| `read_written` | `plain` | `T1:E0=1` | Sometimes | Sometimes |
| `unwritten_value` | `plain` | `T1:E0=2` | Never | Never |

各查询的独立推导如下：

- `read_initial`：读在 worker 写之前可取得初始化 0，另一执行又可读到 1；线程创建调用的先后不等于两个 worker 访存的先后。
- `read_written`：worker 写 1 后另一个 worker 读取可见 1，也存在读到初始化 0 的执行；两架构都允许。
- `unwritten_value`：投影中只有初始化写 0 和一次写 1；读值必须来自对应位置的写，2 没有写来源。

## 单对象查询的覆盖范围

正向查询分别确认旧值和新值可达，反向查询确认没有写来源的 2 不可达。这里检验对象身份、初值及读写投影，没有双对象保序差异，不把两架构相同结果包装成弱内存风险差分。

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
