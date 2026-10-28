# B01：SPSC 环形队列

## 场景与实现

DPDK 使用 ring 进行应用间通信和内存池管理，[官方工程说明](https://doc.dpdk.org/guides-24.11/prog_guide/ring_lib.html)给出固定容量、head/tail、批量操作和 SP/SC 模式。

本例采用单生产者、单消费者和 8 字节元素，把序号与校验值打包为 uint64，模拟工作线程之间的任务标识传递。算法来自上游，pthread 工作负载由本项目补充。

主输入为 [benchmark.c](benchmark.c)，算法为 vendor 中原始 `rte_ring_elem_pvt.h` 和 `rte_ring_c11_pvt.h`，来源及构建适配见 [provenance.md](provenance.md)。

## 线程交互与共享对象

生产者执行 enqueue → do_enqueue_elem → move_prod_head → enqueue_elems → update_tail，先预留 head 和写载荷，再 release 发布 prod.tail。

消费者 acquire 观察 prod.tail，复制元素后 release 归还 cons.tail；生产者 acquire 观察归还进度后才复用槽位。原始分支、复制循环和数组环绕均保留。

共享对象包括 size/mask/capacity、四个原子 head/tail 和普通 uint64 元素数组。配置运行期间只读，各侧拥有自己的 head；统计由单个 worker 写，main 在 join 后读。

启动门只在工作开始前使用；异常标记为 relaxed 原子。消息路径没有额外互斥或逐消息同步。

## 编译、运行与参数

- 在本目录执行 `bash build.sh`，然后 `timeout 30s ../build/B01_spsc_ring`。默认 N=100000、物理 size=8、可用容量 7、最大批量 5、主动让步间隔 64。
- 最小容量：`timeout 30s ../build/B01_spsc_ring --size 2 --batch 1 --iterations 20000`。
- 索引溢出：`timeout 30s ../build/B01_spsc_ring --size 8 --batch 7 --initial-index 4294967280 --iterations 100000`。
- 参数范围：size 为 2..65536 的二次幂，batch 为 1..8 且 ≤size−1，iterations 为 1..10000000；initial-index 为 uint32。yield-every=0 关闭主动让步。

## 行为检查与退出码

preflight 在线程启动前检查空队列拒绝出队、填满、满队列拒绝入队和顺序排空，再于静止状态重置；这些是顺序 API 边界检查。

并发阶段逐元素检查序号和校验值；最后检查 produced=consumed=N，四个索引均为 `(initial+N) mod 2^32`。

stdout 输出 JSON，包含四个最终索引 final_indexes、实际满／空等待次数和批量复制跨数组末尾次数。runner 按参数独立比较四个索引。计数依赖调度；一次批量跨边界与物理索引经过数组边界分别理解，不预设固定次数。

原生退出码为 PASS/0、检查失败/1、配置或环境错误/2。外部超时另记 UNKNOWN，不直接推断死锁。

## 独立消费记录检查

可追加 `--trace /path/to/new.messages.jsonl`，由消费者记录原始 uint64 消息，main 在 join 后导出；默认不记录，一键 Benchmark 回归对 B01 baseline 自动启用。轨迹文件必须不存在，写失败返回 2。

在 Case_Regression_Internal 执行 `python3 benchmarks/scripts/fifo_oracle.py /path/to/new.messages.jsonl --iterations N`，独立检查序号、校验值和条数。PASS/0 为本次记录符合预期，FAIL/1 为消息或数量不符，UNKNOWN/2 为缺失或不可读证据。

轨迹缓冲由消费者独占，不增加消息间同步；额外记录可能改变调度，每条消息占 8 字节缓冲，最大合法 N 需要约 80 MB。原始轨迹、哈希和独立检查结果随本次结果保留。

## Oracle 与对照

[oracle.md](oracle.md)说明不变量与推导，[oracle.json](oracle.json)保存机器预期。在仓库根目录执行 `bash benchmarks/run.sh` 后查看本地 `results/benchmarks/summary.md`，其中记录实际观测；报告由 Git 忽略。

`BENCH_INJECT_CORRUPTION=1 bash build.sh ../build/B01_corruption`，再运行 `../build/B01_corruption --iterations 1000`，应返回 FAIL/1；这是载荷损坏的检查器控制。

model/publication.* 检查发布，model/recycling.* 检查归还。手写事件投影省略完整数组、索引和循环，relaxed/ordered 是人工模型对照，不是上游历史缺陷。

## 当前覆盖与后续工作

已提供固定来源、源码、复现、边界与并发检查、独立 FIFO 轨迹复核、负向控制和模型投影；未接入前端自动提取。

工具后续需要支持数组／指针、调用、运行时写值、算术及值关系、分支循环和同步。文件中保留的 MP/MC 代码不表示本例已覆盖多生产者或多消费者。

行为依据为 DRAFT_WITH_EVIDENCE，架构 Oracle 审查与完整程序模型验证为 UNKNOWN。一次运行通过不证明无限执行、任意配置或任意编译器正确。

本例通过固定来源的真实队列独立检验消息传递与槽位复用。后续重点是将这些语义完整保留到工具链中。
