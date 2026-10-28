# B01：正确性要求与独立 Oracle

## 验证性质

- B01-PUB：消费者读取已发布消息时，载荷来自相应发布；B01-RECYCLE：消费者复制完旧消息后，生产者才可覆写同一槽位。
- B01-FIFO：本次运行收到的完整消息序列严格为 1..N，计数和四个最终索引一致；B01-BOUNDARY：合法配置下空满 API 与对象生命周期满足使用前提。
- 机器预期见 [oracle.json](oracle.json)。在仓库根目录执行 `bash benchmarks/run.sh` 后查看本地 `results/benchmarks/summary.md`；报告由 Git 忽略。Oracle 在运行前定义，实际观察保存在运行目录；比较 PASS 只适用于对应检查。

## 输入、前提与逻辑位置

算法取自 DPDK v24.11、提交 `1b3bf1128d9bda5595861814792f74b8f57160c8` 的 SP/SC、8 字节元素、C11 分支；来源与适配见 [provenance.md](provenance.md)。线程、负载、断言和消费记录是本项目补充。

前提：恰好一个生产者、一个消费者；size 为 2..65536 的二次幂，capacity=size−1，1≤batch≤min(8,capacity)，1≤N≤10000000，initial 为 uint32；初始化、reset、销毁均无并发访问，线程创建和 join 成功。

第 k 条消息的逻辑位置为 `L(k)=initial+k−1`，物理槽位为 `L(k) mod size`；该槽位下一次复用对应消息 k+size。四个 head/tail 保存逻辑进度的 uint32 模值；size 是槽位数，capacity 是最大可用元素数，两者不混用。

推导中的逻辑位置用于区分代次，不能仅靠相等的 uint32 值断言属于同一轮。程序没有输出完整的 head/tail 事件轨迹；本次 N 小于 2^32，但仍可能因 initial 接近上界而发生索引溢出。

## B01-PUB：消息发布

P1：生产者在 `__rte_ring_do_enqueue_elem` 中完成目标元素的普通写；P2：`__rte_ring_update_tail(&r->prod,...)` 以 release 更新 prod.tail。

P3：消费者在 `__rte_ring_move_cons_head` 中以 acquire 读取 prod.tail；P4：`__rte_ring_do_dequeue_elem` 将元素复制到消费者私有 data[8]。P3 必须接收覆盖该消息的 P2，或同一生产者后续覆盖该消息的发布；只读取初始 tail 不满足前提。

依据：P1 sequenced-before P2，P2 synchronizes-with P3，P3 sequenced-before P4，因此 P1 happens-before P4。载荷在读取前不被下一代覆写，还依赖 B01-RECYCLE，不能仅凭发布链推出完整队列安全。

允许：尚未发布时返回空并重试；接收覆盖目标消息的更晚批次。禁止：在这些前提成立时，P4 得到旧值、未初始化值或错误载荷。

源码锚点见 [C11 head/tail 操作](../vendor/dpdk/rte_ring_c11_pvt.h) 和 [元素复制与发布顺序](../vendor/dpdk/rte_ring_elem_pvt.h)。顺序依据为 N1570 §5.1.2.4、§7.17.3；依据中不把普通变量值相等直接当作 reads-from 证明。

已覆盖：publication 两架构的局部投影；原生 FIFO 检查可发现部分结果异常，但不能独立判断异常是否由发布引起。缺口：完整数组、head 预留、批量、分支循环及编译器映射；下一步先评审 P1-P4 与 litmus 目标是否对应。

## B01-RECYCLE：槽位归还

R1：消费者在队列函数内部把旧代载荷完整复制到私有 data[8]；R2：以 release 更新 cons.tail。R3：生产者在 `__rte_ring_move_prod_head` 中以 acquire 接收覆盖该槽位的归还；R4：向该物理槽位写下一代载荷。

依据：R1 sequenced-before R2，R2 synchronizes-with R3，R3 sequenced-before R4，因此旧代读取 happens-before 新代覆写。这里连接的是同一物理槽位的相邻代次；capacity 检查、索引计算和归还值必须确实允许该次复用。

消费者在队列函数返回前已完成复制并归还。返回驱动后的逐条校验和可选记录只读取私有 data[8]，不再占用环形数组槽位；不能把“校验完成”误当成上游归还点。

允许：队列满时返回 0 并重试；正确归还后写入下一代。禁止：旧代复制尚未完成就覆写相同槽位。

源码锚点为 `__rte_ring_do_dequeue_elem`、`__rte_ring_update_tail` 和 `__rte_ring_move_prod_head`；依据同为 N1570 §5.1.2.4、§7.17.3。

已覆盖：recycling 局部排序投影。缺口：多轮槽位所有权、批量和无符号代次关系；当前没有独立识别每次归还与覆写的原生事件记录，不能由 FIFO PASS 宣布该义务完整通过。

## B01-FIFO：消息公式与禁止结果

第 k 条消息满足 `1≤k≤N`，高 32 位为 k；低 32 位为 `((k×2654435761) mod 2^32) xor 0xa5a55a5a`。完整值为高低两部分拼接所得的 uint64。

固定算术样例：k=1 对应 5294400491；k=2 对应 11170195768；k=3 对应 15015819081。这些常量作为检查器测试向量保存，不从本次工具输出反填。

禁止：第 k 个记录的高 32 位不等于 k，低 32 位不等于独立公式，或记录数不等于 N。由此可发现记录中的重复、乱序、旧槽位值、载荷损坏，以及少记录和多记录。

完成条件还包括 produced=consumed=N，以及 prod.head、prod.tail、cons.head、cons.tail 全部等于 `(initial+N) mod 2^32`。仅计数相等不足以证明序列正确，所有索引检查均在 join 后进行。

允许：生产与消费的批量切分不同、等待次数不同、复制跨边界次数不同；这些统计不作为必须达到固定值的 Oracle。不用两个异步索引快照直接断言瞬时占用量。

## B01-FIFO：独立消费记录

原有 C 消费者仍逐条断言；可选 `--trace /path/to/new.messages.jsonl` 另保存每个实际消费值。记录缓冲只由消费者写，main 在两个 join 后输出文件，每条消息不做文件 I/O，也不增加跨线程同步。

轨迹首行为 `{"schema":"b01-fifo-trace-1"}`，之后每行一个十进制 uint64；行位置就是期望序号。轨迹不携带由 C 生成的“正确答案”。记录文件必须是新文件，写失败返回 2，已有记录不覆盖。

`scripts/fifo_oracle.py` 在 Python 中分拆观察值的高低位，按独立公式检查序号、校验和条数，不调用 C 的 message()。公式与格式固定在 `oracle.json` 的 `fifo_contract`，缺失或无依据改动会被运行前检查拒绝。

一键 Benchmark 回归对全部 B01 baseline 工作负载自动启用记录，`result.json` 的 fifo_check 保存状态、总条数、首批错误、路径和 SHA256。轨迹缺失或格式不可读保持 UNKNOWN；可读轨迹违反消息或数量判据为 FAIL。

独立复查命令：在 Case_Regression_Internal 执行 `python3 benchmarks/scripts/fifo_oracle.py /path/to/run.messages.jsonl --iterations N`；N 取实际运行命令的参数，不能由轨迹自报总数。

检查器覆盖：固定向量、重复、乱序、旧槽位值、校验错误、缺项、多项及缺失/损坏记录。集成测试在临时副本中修改双方共用的 C 编码常量，确认 C 自检可 PASS 而独立检查 FAIL，实际主输入不作该修改。

边界：该证据仍来自消费者的观测记录，不是独立硬件观测；记录会增加消费者工作量，可能改变调度。它消除了共用 C 编码函数造成的一类共同错误，不穷尽所有交错，也不单独证明发布、复用或无限执行正确。

## B01-BOUNDARY：边界与生命周期

顺序 preflight：空队列出队返回 0；连续 capacity 次单元素入队均返回 1；再入队返回 0；按序排空 capacity 个元素；再次出队返回 0。任何一步不符合则 FAIL/1，工作线程不启动。

preflight 前后均在无 worker 状态 reset；生产者和消费者启动前完成配置及内存初始化，全部 join 成功后检查最终状态、导出可选轨迹并释放内存。当前生命周期依据为源码路径核对，不是完整动态证明。

参数 Oracle：非法 size、batch、N 等返回 2；默认回归实际覆盖非二次幂 size 和 batch 超过 capacity 两项。分配、线程、轨迹 I/O 等环境错误也可返回 2，不能只凭这个退出码判断发生了参数拒绝。

基础运行矩阵：size=2/batch=1/N=20000；size=8/batch=5/N=100000；size=8/batch=7/N=100000/initial=4294967280；size=64/batch=8/N=50000。各自按 GCC/Clang 的 -O0、-O2 构建运行；实际编译器与配置以日志为准。

已覆盖：这些配置的顺序空满检查、并发消费轨迹和最终状态。缺口：全部合法/非法参数组合、环境失败路径、所有并发边界与进展性质；超时保留 UNKNOWN，不直接断言死锁或不正确。

## publication 硬件投影

初值 data=0、tail=0；P0 执行写 data=1、发布 tail=1；P1 先读 tail，再读 data。目标为“P1 读 tail=1 且 data=0”，tail=1 只有一个写来源，可定位为发布事件。

ordered 推导：载荷写先于发布写，接收发布先于载荷读；目标还要求载荷读取得初始化值，结合对应模型的读值/一致性约束会形成矛盾。完整的允许性仍按指定 CAT 查询。

RISC-V ordered 以发布前 `fence rw,w`、接收后 `fence r,rw` 保序，预期 Never；relaxed 去掉两处 fence，预期 Sometimes。x86 两版均使用 MOV，相关顺序由 TSO 保留，预期均 Never。

目标和初值见 [publication.ordered.riscv.litmus](model/publication.ordered.riscv.litmus) 及相邻三份变体；预期逐架构保存在 `oracle.json`。此处的 Never/Sometimes 是模型允许性，不是原生运行频率。

## recycling 硬件投影

初值 data=1、tail=0；P0 表示消费者，先读旧载荷、再归还 tail=1；P1 表示生产者，先读 tail、再覆写 data=2。目标为“P0 读 data=2 且 P1 读 tail=1”。

ordered 推导：旧代读先于归还写，归还写经接收先于新代写；若旧代读取得该新代写值，就与这些顺序及模型读值约束冲突。目标中的 tail=1 定位到本例唯一归还写。

RISC-V ordered 使用同样的 release/acquire fence，预期 Never；relaxed 无 fence，预期 Sometimes。x86 两版 MOV 保留读→写顺序，预期均 Never。

目标和初值见 [recycling.ordered.riscv.litmus](model/recycling.ordered.riscv.litmus) 及相邻三份变体。局部 data/tail 使用架构字访问，省略真实 uint64 宽度、数组、批量、循环、额外 head fence 与代次；这不是编译器输出的等价证明。

## 参考依据与适用范围

[C11 委员会草案 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)：§5.1.2.4 p11 的 release/acquire 同步、p18 的 happens-before、p25 的数据竞争；§6.2.5 p9 的无符号模运算；§7.17.3 的原子内存序。源码顺序推导与架构映射分开核对。

[DPDK 固定源码](https://github.com/DPDK/dpdk/blob/1b3bf1128d9bda5595861814792f74b8f57160c8/lib/ring/rte_ring_c11_pvt.h)：v24.11，核对 head 预留、tail 更新与 SP/SC 路径；本地 `vendor/manifest.json` 记录原始哈希，元素复制顺序还须核对 `rte_ring_elem_pvt.h`。

[RVWMO 规范](https://docs.riscv.org/reference/isa/v20260120/unpriv/rvwmo.html)：ISA v20260120、RVWMO 2.0，§17.1.1 的 preserved program order 与读值等公理；[说明材料](https://docs.riscv.org/reference/isa/v20260120/unpriv/mm-eplan.html) §37.1.3.6 和 Table 16 支持本例手写 Load/Store/fence 映射，说明材料与规范正文地位不同。

[herdtools7 7.58 x86tso.cat](https://github.com/herd/herdtools7/blob/7.58/herd/libdir/x86tso.cat)：支持指定 x86 模型查询；本次实际 CAT 及 include 闭包以 `result.json` 的路径和哈希为准，模型与所引用规范的一致性仍需审查。

## 对照、比较与审查状态

baseline：正确实现的有界负载；checker_corruption：人为损坏第一条消息，预期程序 FAIL/1、比较 PASS，只证明检查器能发现该错误。独立检查器的错误轨迹测试另列，不冒充真实并发故障。

relaxed/ordered：手写硬件问题与修复对照；x86 两版相同，不能据此宣称 x86 对照证明了修复敏感性。源码级弱化同步问题版暂缺，因为普通载荷可能产生语言层数据竞争。

结构状态为 UNKNOWN（尚未接入核心前端）；行为依据为 DRAFT_WITH_EVIDENCE；架构 Oracle 正式审查及完整程序验证仍为 UNKNOWN。局部投影比较 PASS 与正式审查状态分别记录。

[reviews.json](reviews.json) 仅保存真实发生的评审；本次技术核查、检查器测试和实验不填成团队评审。版本绑定与失效规则见 [Oracle 维护说明](../ORACLE_GUIDE.md)。

## 验收与后续工作

完成标准是四项性质的前提、独立预期、推导、源码和本次检查可逐项对应，缺失证据不计为通过。当前优先复核独立 FIFO 轨迹与局部投影，后续补齐多轮槽位关系和完整程序验证。
