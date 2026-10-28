# 三层正确性验证说明

## 场景清单与正确性要求

- [correctness_manifest.json](correctness_manifest.json) 固定记录 C01–C08、P01–P03、B01/B02 共十三例的输入、独立 Oracle 和说明，缺文件不能因目录扫描而被忽略。
- C01–C08：保留各例 `expected.json` 的对象、初值、事件、内存序、切片、绑定、调用及条件预期。C03 保留分配成功路径和 join 后 free 的前提；C08 还需与 C07 做保留语义的单元等价比较。禁止漏掉关键事件或改变其含义。
- P01：SB 目标在两架构预期 Sometimes；P02：保留 seq_cst fence 时目标预期 Never，去 fence 对照恢复 Sometimes；P03：保留三线程同步和值依赖时，传递成功却读旧 data 的目标预期 Never。范围均为明确映射的硬件事件投影。
- B01：分别检查 B01-PUB 发布、B01-RECYCLE 槽位归还、B01-FIFO 消息及索引、B01-BOUNDARY 边界与生命周期。B02：分别检查 B02-MUTEX 互斥、B02-HANDOFF 可见性、B02-RECORD 记录关系、B02-BOUNDARY 边界与生命周期。详细允许/禁止行为见各例 `oracle.md`。

## 三层依据与结果

- 内部结构 Oracle：C01–C08、P01–P03 依据独立 `expected.json` 比较抽取和切片；B01/B02 尚未接入前端，结构 UNKNOWN。
- Benchmark 行为依据：B01/B02 为 DRAFT_WITH_EVIDENCE，原生比较单独记录；内部结构用例没有完整程序行为 Oracle，不能从结构 PASS 填入行为通过。
- 架构级 Oracle：实际 Never/Sometimes/Always、与预期的比较、正式审查及结论范围分列。P01–P03 保留既有映射实验结果，但没有正式审查记录时架构结论仍 UNKNOWN。B01/B02 使用带版本绑定的 `reviews.json`，规则见 [Oracle 维护说明](benchmarks/ORACLE_GUIDE.md)。
- C01–C08 新增独立 architecture.json/md，覆盖单对象读值与 MP 保序，合计 28 项查询、56 次模型比较；结构预期继续保留。独立执行及审查规则见[C系列架构说明](C_ARCHITECTURE.md)。

## 语言模型与架构映射边界

C01–C08 和 P01 的普通共享访问可能构成语言层数据竞争；这些输入用于静态结构或硬件投影，不执行来推断 C 并发允许结果。依据为 [C11 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf) §5.1.2.4；原子同步与 CAS 另参见 §7.17.3、§7.17.7.4。

acquire/release 的依据必须说明接收的是对应发布及对象代次，而不能仅凭源码存在两个关键字断言同步。Benchmark JSON 中的 reasoning 是限定前提下的人工推导，规范与源码支持范围逐项列出。

RISC-V 手工 Load/Store/fence 映射参考 [RVWMO 说明](https://docs.riscv.org/reference/isa/v20260120/unpriv/mm-eplan.html) 的 Fences 与 Table 16；允许执行由本次实际 CAT 文件约束。模型快照与规范版本一致性仍属于架构审查内容。

硬件事件投影省略的控制流、数组、CAS 写回和多轮关系单独登记；有限模型的 Never 不扩展为无限轮程序证明。原生未观察到异常也不证明该异常不可能发生。

## 执行与复现

在 Case_Regression_Internal 执行 `python3 scripts/run_correctness.py`。它依次运行结构、原型、Benchmark 及 C 系列架构查询，后者复用本次结构结果；在 `results/correctness/<run-id>/` 保存四套输出、启动命令日志及统一 summary.json/summary.md，仍报告 13 个 Case，不覆盖历史目录。

`--out /path/to/new-directory` 指定空输出目录，不更新本地共用入口。默认运行更新 `results/correctness/summary.md` 和 `latest.json`；生成 Benchmark 报告后，同步更新共用的 `results/benchmarks/summary.md` 和 `latest.json`。仅汇总旧证据的 `--collect` 不更新 Benchmark 入口。上述运行目录及入口均由 Git 忽略，报告需在本地执行后查看；版本管理范围见 [结果文件与版本管理](README.md#结果文件与版本管理)。依赖沿用既有 Clang、herd7、GCC/Clang 和 Python 环境，不安装新平台。

只汇总既有证据时执行 `python3 scripts/run_correctness.py --collect --internal /path/to/internal --prototype /path/to/prototype --benchmarks /path/to/benchmarks --out /path/to/new-report`。来源或 Oracle 哈希变化、缺结果、旧版缺少分层字段的 Benchmark 记录均标 UNKNOWN。

Benchmark 重新汇总还要求 `benchmark-evidence-1` 产物清单及相应日志、轨迹和协议文件，并校验当前 CAT include 闭包。汇总器重新计算检查与分层状态；只保留输入快照和结果 JSON 不算有效执行证据。详细格式与状态规则见 [Oracle 维护说明](benchmarks/ORACLE_GUIDE.md#执行证据与重新汇总)。

完整回归执行 `source ../.tools/case-regression-env.sh` 后运行 `python3 -m unittest discover -s tests -v`。独立交付检查仍为 `python3 benchmarks/scripts/check_delivery.py`。

## 汇总状态与验收范围

`execution_comparison_status` 和退出码表示本次已声明检查与预期是否一致：PASS/0、FAIL/1、UNKNOWN/2。架构审查 UNKNOWN 不会把一次确实匹配的实验改成 FAIL；它也不会被执行 PASS 自动提升。

`summary.json` 的 cases 保留三层信息、证据来源、当前来源校验状态与每项剩余缺口。三层状态不压缩成“程序整体正确”。比较不匹配按 FAIL 保留，证据不足按 UNKNOWN 保留。

当前 P01–P03 原型结果只记录顶层模型哈希；C01–C08 独立架构入口和 Benchmark 记录 CAT include 闭包。统一报告保留这一证据差异，不把 P01–P03 包装为同等级架构审查。

## 后续验证

先以 B01 的发布和复用义务开展审查，再独立审查 B02 的交接可见性。B02-MUTEX 已补手工有限 SC 协议，覆盖 CAS 原子性、失败/等待/重置，含两个错误反例；仍需审查源码映射并扩展 C11/RVWMO 完整语义。B02-RECORD 另有独立逐次更新轨迹，不能与互斥状态混用。

核心前端稳定后再根据完整输入暴露的数组、循环、算术、调用、CAS 和路径语义接入。当前 EventIR/VU 仅作内部接口参考，不作为正式冻结接口。

本轮交付包括材料、机器格式、状态处理、执行和回归证据；正式团队评审、完整程序证明、公平性/无饥饿及 Case Factory 扩展按各自前提推进。

## 验收与后续工作

完成标准是每项要求能关联独立依据及本次检查或明确缺口。下一步优先完成逐义务评审，再按完整语义需求衔接核心前端。
