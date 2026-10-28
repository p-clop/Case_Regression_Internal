# 内部 Case 草案

本目录依据《Case_Regression_新成员交接文档_20260918_更新版》建立，**不属于准公开 Team Repo**。`cases/` 中的 C 文件用于前端静态抽取和自动回归，不执行这些原始 C 程序来推断并发结果。普通变量跨线程读写可能构成 C 语言层的数据竞争；新增 `benchmarks/` 的独立运行范围见对应说明。

当前 Team Repo 的 CLI 仍是受限 C 链路。本目录的独立前端已将八个原始 Case 接入自动结构回归，结果不能视作团队核心前端已完成集成。

## 材料索引

- `case_format.md`：每个 Case 的记录格式与状态口径。
- `case_matrix.md`：当前 8 个 Case 的覆盖维度与结构/模型状态。
- `cases/Cxx_*/case.c`：输入源码。
- `cases/Cxx_*/expected.md`：独立于工具输出写出的人工预期。
- `cases/Cxx_*/expected.json`：人工预期的机器可读版本，用于逐字段比较。

## 三层正确性验证

[三层验证说明](CORRECTNESS.md)明确十三例的要求、允许与禁止行为、语言与架构边界；两个 Benchmark 共维护八项独立正确性义务。

执行 `python3 scripts/run_correctness.py`，运行结构、原型和 Benchmark 并保存独立证据；运行后查看本地 `results/correctness/summary.md`，其中分别报告结构、行为依据、架构比较和审查状态。

源码级对照、完整协议和未审查结论的缺口逐项记录，模型比较 PASS 不会自动提升 Oracle 审查状态。

## 工程 Benchmark

[Benchmark 入口](benchmarks/README.md)包含 DPDK SPSC 环形队列、自旋锁的固定来源、可编译源码、独立运行与行为依据；执行 `bash benchmarks/run.sh` 可复现。

运行后查看本地 `results/benchmarks/summary.md`，其中分别记录原生行为检查和硬件事件投影。完整程序模型验证与架构 Oracle 审查保持 UNKNOWN；本轮未接入前端自动提取。

## 八个内部 Case 的自动回归

运行 `bash scripts/run_internal_regression.sh`，比较共享对象、事件、切片保留/删除、Verification Unit 和参数/别名/调用关系。
完整输出格式与外部前端接入方式见 [自动回归说明](README_internal_regression.md)，实际结果见 [八例结果表](results/internal/summary.md)。

结构结果与硬件模型结果分别记录；C01–C08 新增独立 `architecture.json` 与推导，执行 `bash scripts/run_c_architecture.sh`，运行后查看本地 `results/c_architecture/summary.md`。判据及边界见 [C 系列架构说明](C_ARCHITECTURE.md)。正式审查继续 UNKNOWN，结构入口不执行这组模型查询。

## 独立原型与三类完整示例

本目录新增独立的 `prototype/`，使用 Clang AST 抽取有界 pthread/Atomic/Fence 输入，并实际运行 x86-TSO/RVWMO 模型。
P01–P03 分别覆盖普通 pthread、Atomic/Fence 和三线程 release/acquire 传递；人工 Oracle 与原有 C01–C08 分开维护。

运行 `bash scripts/run_prototype.sh`。安装说明、输出解释和能力边界见 [独立原型说明](README_prototype.md)，最近运行结果见 [原型回归结果](results/prototype/summary.md)。

## 结果文件与版本管理

源码、脚本、测试、独立 Oracle、来源记录和固定版本的 vendor 文件纳入版本管理。已有 `results/internal/`、`results/prototype/` 基线继续保留。

`results/correctness/`、`results/c_architecture/`、`results/benchmarks/` 和 `results/review_*/` 为本地运行输出，整个目录由 Git 忽略，包括 `summary.md`、`latest.json`、日志和轨迹；新检出仓库需执行对应命令生成报告。各类结果目录中的 `bin/` 同样忽略。

需要复核或交付某次运行时，保留该运行的完整证据目录；只保留 PASS 摘要不足以重新汇总。源码及材料版本仍须与证据匹配，具体校验见 [Oracle 维护说明](benchmarks/ORACLE_GUIDE.md#执行证据与重新汇总)。本地旧运行可在确认完整有效的证据已保留后再归档或删除。
