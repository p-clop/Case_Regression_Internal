# Case 记录格式

每个 Case 存放 `case.c`、`expected.md` 与机器可读的 `expected.json`。先写人工预期，再接入工具输出；不要从工具结果反推预期。
当前 C01–C08 的结构 Oracle 使用 `schema_version: 2`、`validation: "structure"`。
字段格式、实际产物和接入命令见 [自动回归说明](README_internal_regression.md)。

```md
# Case ID：简短名称

- 目的：
- 输入能力前提：
- Thread Context：入口、可达 helper
- Shared Object：对象、来源、Field Path、别名不确定性
- 预期事件：按线程列出 Load / Store / Atomic / Fence 与对象
- 预期保留：进入候选切片和 Verification Unit 的事件、必要顺序或依赖
- 预期删除：与目标无关的事件和计算，并说明原因
- 目标结果：若有，写清读值与初始值
- x86-TSO / RVWMO：有可信模型 Oracle 才填写；否则 UNKNOWN
- 实际结果：工具版本、输入、命令、输出路径和结论
- 状态：PASS / FAIL / UNKNOWN；注明原因
```

`PASS`：当前能力范围内实际结果与人工预期一致。`FAIL`：当前能力范围内出现可复现差异。`UNKNOWN`：前端未接入、预期尚未确认或模型尚未运行；需要写明原因。

人工预期关注结构和切片，不将抽象 litmus 的模型结果直接视作原始 C 程序的行为保证。

自动结果中 `status` 表示声明的验证范围；C01–C08 的 `scope` 为 `structure_only`。
共享对象、事件、切片、Verification Unit 与绑定/调用分别记录 PASS/FAIL/UNKNOWN；模型状态放在独立的 `verification` 字段中。
结构 PASS 与模型 UNKNOWN 可以同时成立。缺少经过审查的模型 Oracle 时，不能把模型项改成 PASS。

## C 系列架构判据与模型比较

每例新增 `architecture.json`、`architecture.md`、`architecture_reviews.json`；`expected.json` 仍定义结构，其旧 `expected_observations` 占位不作为架构预期。独立入口及查询格式见[C系列架构说明](C_ARCHITECTURE.md)。

独立架构结果中 `comparison_status` 可以在正式审查前为 PASS，`review_status` 及 `conclusion_status` 仍为 UNKNOWN；原结构入口 verification 字段保持 UNKNOWN。不得把这三个状态压成一个“模型通过”。

## 正确性记录

每例 `expected.md` 说明核心要求与结论边界，`expected.json` 继续使用独立人工结构预期；新增行为或架构结论不能反向改变原有结构 Oracle。

[三层验证说明](CORRECTNESS.md)与 `correctness_manifest.json` 固定关联十三例材料。Benchmark 使用带义务编号的独立契约，记录前提、允许/禁止行为、风险、源码、规范、检查与剩余缺口。

实际模型观察、与预期比较、正式审查状态和完整程序验证分别记录；UNKNOWN 填明原因与下一步，FAIL 不因缺少正式审查而被抹去。
