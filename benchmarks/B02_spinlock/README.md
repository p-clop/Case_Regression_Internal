# B02：CAS 自旋锁

## 场景与实现

DPDK 提供自旋锁保护短临界区共享状态。本例用两个 worker 更新“已处理数量＋校验值”记录，模拟受保护的共享进度更新。

来源为 DPDK v24.11 通用原子实现；[官方源码说明](https://doc.dpdk.org/api-24.11/rte__spinlock_8h_source.html)用于解释，固定版本以 [provenance.md](provenance.md)为准。

[benchmark.c](benchmark.c)保留 worker → lock → update_record → unlock 调用链、多轮循环、竞争等待和重试，写入值由共享记录计算得到。

## 共享对象与线程交互

locked 是原子 int，初始 0；count/checksum 是普通 uint64，运行期间的全部访问均持有同一把锁。

strong CAS 0→1 成功为 acquire、失败为 relaxed；失败后 relaxed 等待空闲，expected 重置为 0 再竞争；解锁 release 写 0。这些都执行上游原始函数体。

临界区先检查 checksum(count)，再更新 count+1 和新校验值；线程统计由各 worker 写，main 在 join 后读。启动门仅作用于启动阶段，暂停统计为线程局部变量。

临界区未添加用于检查重叠的额外原子 RMW，避免检查器增加线程间排序。行为检查不单独构成穷尽的互斥证明。

## 编译、运行与参数

- 在本目录执行 `bash build.sh`，然后 `timeout 30s ../build/B02_spinlock`。默认每线程更新 100000 次，每 64 次更新在持锁期间主动让步，增加竞争机会。
- 关闭主动让步：`timeout 30s ../build/B02_spinlock --iterations 20000 --yield-every 0`。
- iterations 范围为 1..10000000，含义是每线程次数；yield-every 为 uint32，0 表示关闭主动让步。
- stdout 输出 JSON，包含每线程 completed/errors/wait_pauses、最终 count/checksum 和 locked。runner 按次数独立比较 checksum 及锁空闲状态。wait_pauses>0 表示实际执行过等待循环，其数值不是性能指标。

## 行为检查与负向控制

顺序 preflight 检查空闲锁 trylock 成功、持锁时 trylock 失败；并发阶段检查记录不变量，结束检查两个 worker 各完成 N 次、count=2N、checksum 正确、locked=0。

`BENCH_INJECT_CORRUPTION=1 bash build.sh ../build/B02_corruption`，再执行 `../build/B02_corruption --iterations 1000`，应返回 FAIL/1。人为损坏发生在锁内，未增加一个无锁普通共享写。

原生退出码：0 为检查通过，1 为不变量或 preflight 失败，2 为配置或线程环境错误。外部超时单独记录 UNKNOWN。

## Oracle 与模型边界

[oracle.md](oracle.md)给出互斥、更新及可见性依据，[oracle.json](oracle.json)保存预期。在仓库根目录执行 `bash benchmarks/run.sh` 后查看本地 `results/benchmarks/summary.md`，其中记录实际结果；报告由 Git 忽略。

model/handoff.* 仅检查已持锁写入、解锁和后继成功获取之间的发布义务；成功获取的读取投影成 Load，省略 CAS 写回、原子性、失败和重试。

relaxed/ordered 为人工硬件对照，不是上游历史缺陷及补丁；架构 Oracle 审查与完整程序模型验证仍为 UNKNOWN。

## 独立更新记录检查

可追加 `--trace /path/to/new.updates.jsonl`。worker 把每次更新前后值记录到私有缓冲，main 在两次 join 后导出；默认不记录，一键 Benchmark 回归对 B02 baseline 自动启用。

在 Case_Regression_Internal 执行 `python3 benchmarks/scripts/record_oracle.py /path/to/new.updates.jsonl --iterations N`，独立检查前后 checksum、加一关系、线程内顺序、每线程 N 次及完整的 1..2N 提交计数。PASS/0 为本次记录符合预期，FAIL/1 为违反判据，UNKNOWN/2 为缺失或不可靠证据。

文件必须不存在；记录写入失败返回 2。每次更新 32 字节私有缓冲，最大 N 需约 640MB；额外记录延长临界区并影响调度，不增加共享原子检测器，也不用于性能评价。

## 有限获取协议检查

执行 `python3 benchmarks/scripts/spinlock_protocol.py`，或运行既有 Benchmark 入口，检查两线程每线程 1/2/3 次获取的 SC 抽象；包含 CAS 成功、失败写回 expected、等待、重置及解锁。

正确版预期不出现重叠；拆开 CAS 和遗漏 expected 重置两个人工问题版应产生反例。运行结果、状态/转移数和反例自动保存为本次 `B02_spinlock/protocol.json`，比较结果纳入总状态。

协议是手工建立的有限 SC 状态机，不是完整 C11/RVWMO 证明；handoff 投影仍不包含 CAS 写回与重试，两类证据分别记录。`--no-models`仅关闭 herd 硬件投影，有限协议仍执行。

## 当前覆盖与后续工作

本轮包含真实锁、独立更新轨迹、有限协议与错误对照、不同调度配置及硬件投影；未接入前端自动提取。

后续需支持 CAS 读写原子性、成功／失败路径、控制依赖、循环、普通数据锁保护和运行时算术。不能只把 lock/unlock 当作两个标签就认定协议已处理。

本例不承诺公平性、无饥饿或等待上界，不进行吞吐量评价；没有 RISC-V 原生执行证据。

本例通过真实竞争和共享记录更新暴露同步需求。后续重点是完整保留获取、失败重试和临界区范围。
