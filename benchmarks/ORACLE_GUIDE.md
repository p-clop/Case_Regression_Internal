# Benchmark Oracle 维护说明

## 独立预期与必填字段

B01/B02 的 `oracle.json` 使用 `engineering-benchmark-2`，保留既有 `native` 和 `projections` 字段，新增 `references`、`obligations`、`variants` 与 `review_file`。

每项义务必填 id、requirement、preconditions、allowed、forbidden、risk、reasoning、references、`source_anchors`、`native_kinds`、`native_scope`、`projection_checks`、`remaining_gaps` 和 `next_action`。源码锚点使用相对 benchmarks 的路径及符号，避免行号变化造成失效。

`obligations_manifest.json` 固定列出八项必需义务，原生专用义务也不能被遗漏；每项编号还须出现在 `oracle.md`。每个 projection 必须且只能关联一个义务。无独立原生检查或无架构投影的义务使用空列表，其对应检查状态为 UNKNOWN，并说明缺口；不能从其他义务的 PASS 推断它通过。

`python3 scripts/run_suite.py` 在编译前检查格式、引用、源码锚点和投影覆盖。无效或缺失 Oracle 返回 UNKNOWN/2；固定上游或声明投影被篡改仍返回 FAIL/1。

B01 增加固定 `fifo_contract`，记录消费轨迹格式及独立消息公式；与 `scripts/fifo_oracle.py` 不一致或缺失时拒绝执行。全部 B01 baseline 必须有独立消费记录检查，缺失或不可读记录为 UNKNOWN，可读记录中消息/条数不符为 FAIL；其结果属于 B01-FIFO，不提升 B01-PUB/RECYCLE 为完整验证通过。

B02 的 record_contract 固定更新轨迹与独立校验公式，protocol_contract 固定两线程 SC 有限协议的边界和对照预期；任一缺失或改变均拒绝执行。record_check 属于 B02-RECORD；B02-MUTEX 另有 bounded_protocol，比较 PASS 不提升完整验证或架构审查。

## 执行证据与重新汇总

每例 `result.json` 的 `evidence` 使用 `benchmark-evidence-1`，记录 Case 身份、原始输出目录、编译器检查计划，以及相对于本次运行目录的日志、轨迹、协议文件路径和 SHA256。执行命令保留原样；二进制只记录构建信息和哈希，不属于汇总所需产物。保留目录结构复制整套证据后，可以在新位置重新汇总。

独立运行和统一汇总共用 `scripts/benchmark_evidence.py` 的 `validate_benchmark_evidence()`。它校验当前输入与 Oracle、必需检查覆盖、产物哈希和 CAT include 闭包，重新解析原生输出与 Observation，并重跑 FIFO、更新轨迹检查；有限协议按固定检查清单重新比较。分层状态与评审状态由本次校验结果重建，不直接采用旧结果中的 PASS 或 CONFIRMED。

`evidence_validation` 单独记录证据完整性及具体问题。缺失、损坏、过期或旧版无证据清单的记录不能贡献 PASS；可靠观察与当前预期不符记 FAIL，其他项目证据不足不覆盖已确认的 FAIL。仅保留 `inputs.json` 和 `result.json` 不足以恢复执行通过。旧输出需使用空目录重新运行后才能生成新版证据。

## 状态含义

- `expected` 是独立预期，`actual` 是实际模型观察（Never/Sometimes/Always）；`status` 与 `comparison_status` 都表示本次比较（PASS/FAIL/UNKNOWN），保留前者用于兼容旧使用方。
- `oracle_review` 与 `review.status` 表示正式审查（CONFIRMED/UNKNOWN）。无审查记录时，即使比较 PASS，`model_conclusion.status` 仍为 UNKNOWN；比较 FAIL 也会原样保留。
- `model_conclusion` 仅表示已审查预期下的指定硬件投影结论。每项 `full_verification` 和整例 `full_program` 当前仍为 UNKNOWN，因为完整控制流、对象、多轮关系或 CAS 协议没有全部验证。
- 行为依据 `DRAFT_WITH_EVIDENCE`、原生比较 PASS 与正式行为审查 UNKNOWN 可以同时成立。完整性自动检查不能替代材料评审。

## 评审记录

每例 `reviews.json` 使用 `benchmark-reviews-1`，包含 case 与 records；本次 records 均为空。只有实际评审后才添加记录，不填写虚构姓名、日期或意见。

一条记录必填 target、decision=`CONFIRMED`、review_id、reviewer、reviewed_at（含时区的 ISO 时间）、rationale、`subject_sha256`。行为审查 target=`behavior`；架构审查 target 例如 `publication.ordered.riscv`，还须记录 expected 与 model_files。

`subject_sha256` 使用本次 `summary.json` 的 `review_subject_sha256`（分项 correctness.subject_sha256 相同）；架构 model_files 从对应投影结果复制，包括实际 CAT include 闭包。记录应指向审查过的义务、规范、映射与意见，不得仅以一次运行结果作为理由。

同一 target 只维护一条当前记录；重复冲突、身份不完整、输入变化、模型闭包变化、预期变化或缺模型均保持 UNKNOWN，并记录具体原因。既有旧记录可移入独立归档后维护当前记录。

## 审查与输入版本绑定

`review_subject_sha256` 是 benchmarks 输入快照中除 `reviews.json` 外全部文件哈希映射的 SHA256；源码、适配头、文档、Oracle、投影、脚本或检查改变时，旧审查保守失效。两个场景共用此输入快照，因此另一例的材料变化也会使当前审查失效。

`reviews.json` 从 subject 中排除，加入真实审查不会使自身立即失效；完整 `inputs.json` 仍记录 `reviews.json` 的哈希。修改审查记录后重新运行，保留新的执行证据。

文件哈希用于防止过期证据混用，不认证评审人的身份或组织授权。当前框架只保存记录，正式评审仍需真实发生。

## 对照的覆盖范围

baseline 是正确实现及有界工作负载；checker_corruption 是检查器自检，程序应 FAIL/1，而“与负向预期一致”的回归比较应 PASS。

relaxed/ordered 是人工硬件问题与修复对照。x86 的普通 MOV 本身保留相关顺序，因此两变体可同为 Never；RISC-V 删除和恢复 fence 用来检验排序敏感性。

源码级问题/修复对照暂缺；弱化普通载荷同步可能产生 C11 数据竞争。B02 handoff 未包含 CAS 写回、原子性、失败及重试，不能覆盖 B02-MUTEX；B01 投影也不证明 FIFO 或完整多轮复用。

## 执行与回归

在 benchmarks 中执行 `bash run.sh`；上层执行 `python3 scripts/run_correctness.py` 可运行并汇总 C01–C08、P01–P03、B01/B02，见 [三层验证说明](../CORRECTNESS.md)。

B01 原生 JSON 增加四个 final_indexes，B02 增加 locked；runner 独立比较最终索引、count、checksum 与锁状态。新增字段不改变上游算法及临界区内的同步。

在 Case_Regression_Internal 执行 `source ../.tools/case-regression-env.sh` 和 `python3 -m unittest discover -s tests -v`。新增回归检查错误观察、缺材料、旧评审、模型变化与缺失结果，合成评审仅存在测试临时目录。

## 验收与后续工作

完成标准是独立依据与执行证据分别维护，且每项未覆盖义务有明确原因和下一步。后续先开展逐义务审查，再扩展完整语义验证。
