# B02：正确性要求与独立 Oracle

## 验证性质

- B02-MUTEX：最多一个线程持有锁并处于临界区；B02-HANDOFF：后继成功获取后看到对应前驱临界区的写入；B02-RECORD：每次受保护更新正确且形成完整的 1..2N 提交计数；B02-BOUNDARY：初始化、trylock、退出和参数满足使用前提。
- [oracle.json](oracle.json)保存独立预期、消息公式、协议边界与来源。在仓库根目录执行 `bash benchmarks/run.sh` 后查看本地 `results/benchmarks/summary.md`，其中保存本次比较；报告由 Git 忽略。四项性质分别记录，不能用最终计数 PASS 代替互斥或交接可见性证明。

## 实现、初值与分析范围

使用 DPDK v24.11、提交 `1b3bf1128d9bda5595861814792f74b8f57160c8` 的通用 C11 strong CAS 自旋锁；实际编译的机械提取体见 [common/dpdk_spinlock.h](../common/dpdk_spinlock.h)，来源及删改见 [provenance.md](provenance.md)。

两个 worker 各请求 N 次更新，1≤N≤10000000；locked 初值 0，record 初值 `(0, checksum(0))`；初始化在启动前，全部 join 后才读取最终状态并释放可选记录缓冲。

运行期间所有共享 record 访问在同一对象的 lock/unlock 调用之间；这是代码结构约束，实际互斥仍是待检查的性质。只有持有者释放锁，不允许第三方写 locked；创建和 join 成功属于环境前提。

worker 局部 completed/errors/pauses 和可选更新缓冲只由所属线程写；main 在 join 后读。启动门只作用于初次开始，不给每次临界区增加同步。

## B02-MUTEX：CAS 成败路径

M1：每次 lock 调用初始化 exp=0；M2：strong CAS 原子比较 locked 与 exp，成功时写 1 并以 acquire 返回；M3：失败时实际 locked 值写回 exp，失败内存序为 relaxed。

M4：失败路径 relaxed 等待观察 0；M5：将 exp 重置为 0 并重试 CAS；M6：只有 CAS 成功的线程进入临界区，结束后 release 写 0 解锁。观察到 0 本身不是取得锁。

判断依据：同一原子对象的 CAS 读改写不可分割；在持有者释放前，另一个以 exp=0 执行的 CAS 不能把已占用的 1 当作空闲 0 成功获取。依据为 N1570 §7.17.7.4 p2、§7.17.3 和固定源码。

失败写回会让 exp 变为 1。如果漏掉 M5，等待结束后另一线程重新获取，重试可能以 exp=1 成功执行 1→1 并错误进入。若把 M2 拆为普通比较与写入，两线程也可能都先比较成功再进入。

允许：CAS 失败、等待和重试；同一线程连续获取；调度不交替。禁止：两个线程同时处于持锁区间、失败 CAS 直接进入、仅等待到 0 就进入或非持有者解锁。

原生最终计数与更新轨迹不能独立证明本性质；新增有界协议证据专门记录其覆盖，架构 handoff 投影继续不作为互斥证明。

## B02-MUTEX：有界协议模型

手工模型位于 [spinlock_protocol.py](../scripts/spinlock_protocol.py)。状态包括 locked，以及每个 worker 的 pc、expected、已完成轮数。源码映射为 CAS→wait→reset→CAS，成功后 critical→unlock，下一次调用重新初始化 expected=0。

正确版 CAS 的比较与写 1 是一个转移；失败转移写回 expected。wait 读非 0 是停留原状态，读 0 进入 reset；reset 与下一次 CAS 分开，允许另一个线程在中间竞争。

判据为所有可达状态中处于 critical 或 unlock 的线程数≤1，且存在持有者时 locked=1；unlock 状态表示临界区结束但尚未执行 release 写 0，仍计作持有者。

正确版分别穷举两线程、每线程 1/2/3 次获取的有限状态图；已访问状态合并，等待自环不无限展开。只判定安全性，不从存在完成状态推断所有调度都完成，也不作公平性或无饥饿承诺。

错误对照 split_cas 把比较与写 1 拆开；missing_expected_reset 省略失败重试前的 exp=0，保留每次新调用的初始化。两对照各用两轮，预期出现互斥反例；模型自身性质为 FAIL，而“符合问题版预期”的比较为 PASS。

可执行 `python3 benchmarks/scripts/spinlock_protocol.py`；一键回归自动保存 `B02_spinlock/protocol.json`、完整命令、stdout/stderr、状态数、转移数与具体反例。协议比较缺失为 UNKNOWN，不影响架构审查状态。

模型是单锁 SC 交错抽象，wait 读取当前状态，未建模全部 C11 relaxed 旧值观察、weak memory、编译器 lowering 或真实 ISA CAS；也不包含普通 record 的可见性。源码到状态机映射仍需审查，完整程序验证保留 UNKNOWN。

## 错误对照与预期反例

拆开 CAS：T0 比较 0 成功；T1 也比较 0 成功；T0 写 1 进入；T1 写 1 进入，两个持有者重叠。

漏重置：T0 持锁；T1 失败并得到 exp=1；T0 释放；T1 等待观察 0；T0 再次成功获取；T1 未重置 exp，以 1→1 CAS 成功，两个持有者重叠。

这些是手工协议模型中的人工缺陷。未将失去互斥的普通 C 记录程序当作可靠架构实验来运行；模型反例不冒充上游真实历史漏洞。

## B02-HANDOFF：发布与接收

H1：前一持有者更新普通 count/checksum；H2：release 解锁写 0；H3：后继 acquire CAS 读取对应解锁的 0 并写 1 成功；H4：后继读取普通记录。

在明确对应的解锁与成功接收关系下，H1 sequenced-before H2，H2 synchronizes-with H3，H3 sequenced-before H4，因此 H1 happens-before H4。互斥保证持锁期间没有其他并发更新。

初次获取可能读取初始化 0；相同线程再次获取还存在自身顺序关系。实际程序多次写 0，不能仅凭值等于 0 就认定 H3 读取了指定的 H2；完整多次交接关系仍待验证。

允许失败竞争者 relaxed 等待后重试；禁止在接收相应发布后读取前驱已更新记录的旧值。协议模型只检查获取逻辑，不能替代这项弱内存可见性检查。

## handoff 硬件投影

初值 data=0、tail=1；P0 表示已持锁的线程，写 data=1 后解锁 tail=0；P1 先读 tail 再读 data。目标是“P1 读 tail=0 且 data=0”。tail 初值是 1，唯一写 0 者是 P0 的解锁，可定位目标的接收来源。

ordered 中载荷写先于解锁，接收解锁先于载荷读；目标还要求读旧载荷，与相应模型的保序及读值约束冲突。RISC-V 使用发布前 fence rw,w、接收后 fence r,rw，预期 Never；relaxed 删掉这两处 fence，预期 Sometimes。

x86 两变体均为 MOV，相关顺序由 TSO 保留，目标预期均 Never；相同结果不构成 x86 修复敏感性证据。实际 CAT 查询、include 闭包哈希与允许性结果保存在运行记录。

[handoff.ordered.riscv.litmus](model/handoff.ordered.riscv.litmus) 及另外三份变体只投影成功 CAS 的读取部分，没有写 1、失败或重试，也不是编译器实际输出；抽象架构字宽不等于真实 uint64 记录宽度。协议与投影分别提供证据，尚未证明两者组合等价于完整源码。

## B02-RECORD：独立公式与更新链

校验函数规定为 `C(k)=((k×11400714819323198485) mod 2^64) xor 0x5a5aa5a5deadcafe`；更新必须从 `(k,C(k))` 变为 `(k+1,C(k+1))`。本例最多 2N≤20000000 次，不发生 count 溢出，校验乘法仍按模运算。

固定算术向量：C(0)=6510698343141591806，C(1)=14154211219428849387，C(2)=7364606772616180436，C(3)=9294524224464142017，C(4)=2488031261898324650。检查器测试使用这些固定值，不从本次输出反填。

记录格式每行六项 `[worker, ordinal, before_count, before_checksum, after_count, after_checksum]`；worker 为 0/1，ordinal 为本线程从 1 开始的局部成功更新编号。文件先导出 worker0 的缓冲，再导出 worker1，文件行序不代表全局执行时间。

独立 Python 检查每次前后 checksum、after=before+1、局部 ordinal 连续、同一线程进度不后退。再检查 after_count 的并集恰为 1..2N 且每个只出现一次，每线程恰有 N 项；不要求线程交替。

最终还要求 completed=[N,N]、errors=[0,0]、count=2N、checksum=C(2N)、locked=0。最终状态与更新轨迹分别核对，可发现最终计数正常但中间 checksum 错误的情况。

允许不同的线程先后、让步和等待次数；禁止跳步、重复提交计数、缺失更新、局部逆序、错误的更新前后载荷或最终仍持锁。完整记录通过只说明观测更新链符合要求，不证明所有时刻临界区无重叠。

## B02-RECORD：线程私有轨迹检查

可选参数 `--trace /path/to/new.updates.jsonl` 分配两个 worker 私有缓冲。每次持锁记录 update_record 前后实际值，main 在两个 join 后输出；首行为 `{"schema":"b02-record-trace-1"}`，之后为六项整数数组，不输出自报的正确答案。

[record_oracle.py](../scripts/record_oracle.py)不调用 C checksum()，依据 `record_contract` 中固定公式和外部运行参数 N 检查。缺失或格式不可靠为 UNKNOWN；有效记录违反判据为 FAIL；已经发现的反例不会被后续坏格式降成 UNKNOWN。

一键回归对全部 B02 baseline 自动记录；`result.json` 的 record_check 保存条数、各线程数量、首批错误、缺失提交数、文件路径和 SHA256。独立复查命令为 `python3 benchmarks/scripts/record_oracle.py /path/to/run.updates.jsonl --iterations N`。

检查器测试覆盖完整交错链、重复、跳步、局部逆序、错误前后校验、缺项、多项和损坏记录。临时副本另把 C checksum(1) 同时改错，保持初值与最终校验正确，验证 C 自检及最终状态能通过而独立轨迹检查失败。

文件要求不存在，写失败返回 2，已有记录不覆盖。每次更新增加 32 字节私有缓冲，最大 N 需两线程合计约 640MB；记录会延长持锁时间并影响调度，不用于性能比较，也没有额外共享原子 RMW 检测重叠。

## B02-BOUNDARY：初始化、trylock 与退出

preflight 在线程启动前初始化锁为 0，第一次 trylock 应成功，持锁时第二次应失败，然后释放；失败即 FAIL/1，不启动 worker。该顺序检查不证明并发互斥。

record 在 worker 启动前初始化；worker 每次正常更新和错误退出路径均调用 unlock；main 在全部 join 成功后读最终数据、导出轨迹并释放缓冲。环境失败会退出，不作为算法反例。

N 为 1..10000000，yield-every 为 uint32，0 关闭主动让步。原生 0 表示声明检查通过，1 表示不变量失败，2 表示参数或环境/证据错误；不能仅凭 2 区分参数拒绝、分配失败和轨迹写失败，需结合命令与 stderr。

默认回归覆盖 N=100000/yield-every=64 和 N=20000/yield-every=0，按可用 GCC/Clang 的-O0/-O2 构建；非法配置实际覆盖 N=0。等待计数只记录，不要求必然竞争或固定值；超时保留 UNKNOWN。

缺口包括全部参数和环境错误组合、所有线程调度、无限执行、公平性与无饥饿。协议穷举合并等待自环，并不验证这些进展性质。

## 参考规范与固定来源

[N1570](https://www.open-std.org/jtc1/sc22/WG14/www/docs/n1570.pdf)：§7.17.7.4 p2 支持 CAS 比较、成功写入与失败写回 expected；§5.1.2.4 p11、p18 支持同步与 happens-before；§7.17.3 支持内存序；§6.2.5 p9 支持 unsigned 模运算。

[DPDK固定版本](https://github.com/DPDK/dpdk/blob/1b3bf1128d9bda5595861814792f74b8f57160c8/lib/eal/include/generic/rte_spinlock.h)：核对 strong CAS、exp=0 重置、等待和 release 解锁；来源完整性与机械提取由 `scripts/check_sources.py` 核对。

[RVWMO规范](https://docs.riscv.org/reference/isa/v20260120/unpriv/rvwmo.html)及[说明材料Table16](https://docs.riscv.org/reference/isa/v20260120/unpriv/mm-eplan.html)：ISA v20260120，支持本例手写 Load/Store/fence 关系；说明材料不是规范正文，未据此宣布完整 CAS lowering 已完成。

[herdtools7 7.58 x86tso.cat](https://github.com/herd/herdtools7/blob/7.58/herd/libdir/x86tso.cat)：查询指定模型的允许性；本次实际模型路径、include 闭包哈希、工具版本和目标条件以运行结果为准。

## 正确版、问题对照与审查状态

baseline 提供真实锁与有界更新轨迹；checker_corruption 只在持锁时破坏载荷，预期原生 FAIL/1、比较 PASS。协议错误变体和硬件 relaxed/ordered 均为人工构造，具体范围分别记录，不冒充上游历史缺陷。

原生记录、SC 协议比较、硬件投影比较、正式 Oracle 审查和完整程序验证分别报告；协议缺失或比较失败会影响总执行比较，协议 PASS 不提升架构 Oracle 或完整证明状态。

行为依据保持 DRAFT_WITH_EVIDENCE，核心前端结构为 UNKNOWN，正式架构审查和完整程序验证保持 UNKNOWN。[reviews.json](reviews.json)仅保存真实发生的团队评审，技术核查与自动运行不会代填。

状态和版本绑定规则见 [Oracle维护说明](../ORACLE_GUIDE.md)。本例新的有限协议证据对应 B02-MUTEX，独立更新轨迹对应 B02-RECORD，不能跨性质移用 PASS。

## 验收与后续工作

完成标准是四项性质的前提、推导、判据和本次证据可以逐项复核，问题对照产生预期反例，未覆盖范围明确保留。下一步优先评审源码到有限协议的映射与锁交接来源，再补齐 C11/RVWMO 完整语义验证。
