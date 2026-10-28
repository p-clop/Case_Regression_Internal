# 工程并发 Benchmark

## 场景与实现范围

- [B01_spsc_ring](B01_spsc_ring/README.md)：DPDK SP/SC 元素环形队列，保留消息传递、批量复制、空满判断、槽位复用及索引环绕。
- [B02_spinlock](B02_spinlock/README.md)：DPDK 通用 CAS 自旋锁，保留竞争、等待、重试、临界区更新和锁交接。
- 两例采用同一开源项目中的不同机制；真实算法来自上游，线程工作负载和检查逻辑由本项目补充。完整线程、共享结构、函数调用、分支和循环保留在原生主输入中。

## 环境与运行

- 环境为 Linux、支持 C11 的 GCC 或 Clang、pthread、Python 3.9+；上游源码已随材料保存，构建无需完整 DPDK、EAL、大页或网卡。
- 在本目录执行 `bash run.sh`。默认发现 GCC 和工作区 Clang，分别在 `-O0`、`-O2` 下编译运行；发现 herd7 后执行声明的事件投影。每条命令默认超时 30 秒。
- 单例执行 `bash B01_spsc_ring/build.sh`、`timeout 30s build/B01_spsc_ring`，或 `bash B02_spinlock/build.sh`、`timeout 30s build/B02_spinlock`。
- 指定编译器：`bash run.sh --compiler /usr/bin/gcc --compiler /path/to/clang`。单例构建可用 `CC=/path/to/clang BENCH_OPT=-O0 bash B01_spsc_ring/build.sh`。
- 只运行原生部分：`bash run.sh --no-models`。模型状态为 UNKNOWN，整体退出码为 2，原生结果单独记录。herd7 和模型可用 `--herd7`、`--x86-model`、`--riscv-model` 指定，也支持既有 PROTOTYPE_* 环境变量。

## 执行证据与退出码

- 默认在 `../results/benchmarks/` 新建独立运行目录；运行后查看 `../results/benchmarks/summary.md`，同目录 `latest.json` 是机器可读入口。二者由独立运行与三层统一运行共用，指向最近一次默认运行生成的报告。该目录包含入口在内均由 Git 忽略，版本管理范围见 [结果文件与版本管理](../README.md#结果文件与版本管理)。
- `--out /path/to/new-directory` 可以指定其他空目录，已有结果不覆盖，也不更新本地共用入口；仅汇总旧证据的 `--collect` 不更新 Benchmark 入口。执行中断且未生成报告时，入口保留上一份报告。
- `inputs.json` 保存源码、适配头、脚本、Oracle、文档和 litmus 的 SHA256。每例 `result.json` 保存编译器、构建与执行命令、参数、预期、实际值、比较状态、二进制哈希和日志路径。
- 每次编译、原生运行及模型查询均保存 stdout、stderr、退出码和耗时。模型保存实际引用 CAT 文件及 include 闭包哈希。二进制不入库，可以按命令重建。
- 每例 `evidence` 保存日志、轨迹及协议文件的相对路径和 SHA256；独立运行与 `--collect` 共用证据校验，重新计算比较结果。缺失、损坏、过期或缺少新版清单的证据不能沿用旧 PASS，详见 [证据格式](ORACLE_GUIDE.md#执行证据与重新汇总)。
- B01 baseline 自动导出消费轨迹，由 `scripts/fifo_oracle.py` 独立检查完整序号、校验值和条数；`result.json` 的 fifo_check 保存路径、SHA256 和检查结果。B02 baseline 导出更新前后轨迹，由 `scripts/record_oracle.py` 检查完整更新链，结果见 record_check。缺失记录不算通过。
- B02 另执行 `scripts/spinlock_protocol.py` 的有限 SC 获取协议及两个错误对照，保存 `protocol.json`、命令和反例；比较结果影响总状态，正式审查及完整程序状态继续分列。`--no-models`仅关闭 herd 硬件查询，不关闭此有限协议检查。
- 原生程序退出码：0 为检查通过，1 为检查失败，2 为参数或环境错误；一键运行退出码：0 为执行检查均与预期一致，1 为不匹配，2 为证据不足。超时、未运行均不算成功。

## 来源与完整性检查

来源为 DPDK `v24.11`，提交 `1b3bf1128d9bda5595861814792f74b8f57160c8`。下载 URL、原始路径和文件哈希见 [vendor/manifest.json](vendor/manifest.json)，标签解析原文见 `vendor/tag.json` 和 `release.json`。

七份原始文件保持字节不变，保留版权和 BSD-3-Clause 许可。`python3 scripts/check_sources.py` 校验哈希及机械提取函数；`--write-extracts` 可从已校验来源重建提取头。

`python3 scripts/check_delivery.py` 在临时副本中检查独立构建、源码／内存序篡改拒绝、未运行模型与缺少编译器的 UNKNOWN、旧输出目录拒绝；不修改主输入。

具体适配见 [B01 来源记录](B01_spsc_ring/provenance.md)和 [B02 来源记录](B02_spinlock/provenance.md)。缩减 ring 布局不提供完整 DPDK ABI，不用于性能比较。

## 正确版与对照

- 正确版运行真实并发算法，检查逐条消息或受保护更新的不变量。
- 原生负向对照启用 `BENCH_INJECT_CORRUPTION`，故意破坏载荷或锁内校验值；预期程序 FAIL/1，回归比较 PASS。这只证明检查器能发现错误，不代表上游缺陷。
- 内存序问题／修复对照为人工编写的 relaxed／ordered 硬件投影，检查发布、槽位归还和锁交接的排序义务；它们不是历史漏洞与补丁。
- 未提供弱化同步后的普通载荷 C 问题版，因为这可能产生语言层数据竞争；该版本缺项不以不可靠的原生运行证据替代。

## Oracle 与结论边界

两例各有独立编写的 `oracle.md` 和 `oracle.json`，依据上游算法、不变量和排序推导，未将一次工具输出复制为标准答案；行为依据状态为 DRAFT_WITH_EVIDENCE。现按八项义务关联源码、规范、检查与缺口，机器格式及审查规则见 [Oracle 维护说明](ORACLE_GUIDE.md)。

一键 PASS 仅表示声明的源码检查、有界原生工作负载和事件投影符合预期。`material_checks` 仅表示源码与运行的自动检查通过，人工材料验收还需阅读来源与依据。

`architecture_oracle_review`、`full_program_model_verification` 均保持 UNKNOWN。自旋锁 handoff 硬件投影仍省略 CAS 写回与失败重试；新增有限 SC 协议单独包含这些分支，未证明与完整 C11/RVWMO 程序等价；没有 RISC-V 原生运行证据。

本轮未接入前端自动提取；`reviews.json` 当前为空，不填写虚构的评审人及日期。实际评审后可登记带输入和模型版本绑定的记录。现有 C01–C08、P01–P03 源码和独立预期继续保留。

## 三层验证入口

在上层 Case_Regression_Internal 执行 `python3 scripts/run_correctness.py`，同时保存 C01–C08、P01–P03 和两个 Benchmark 的本次结果，见 [三层验证说明](../CORRECTNESS.md)。

B01-PUB、B01-RECYCLE 与 B02-HANDOFF 分别关联局部排序投影；B02-MUTEX 明确保留 CAS 原子性及失败重试的缺口。每项原生、投影和完整验证状态分别记录。

## 前端集成需求

- B01 暴露结构体／数组、指针、跨函数调用、运行时写入、无符号模运算、分支循环及 acquire/release/fence 需求。
- B02 暴露非常量计算、CAS 原子性、成功／失败路径、等待重试和普通数据锁保护关系。原始主输入未为了适应现有受限前端而改成直线输入。

## 验收与后续工作

完成标准是两个场景来源固定、源码可编译运行、不变量可检查、证据可复核。下一步依据主输入暴露的语义缺口增量扩展前端，再开展完整语义下的集成验证。
