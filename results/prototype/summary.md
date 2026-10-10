# 独立原型回归结果

整体状态：**PASS**。

PASS 表示结构和指定硬件映射的模型结果符合人工 Oracle；不证明原始 C 程序无数据竞争。

| Case | 结构 | x86-TSO | RVWMO | 状态 |
| --- | --- | --- | --- | --- |
| [P01_pthread_sb](P01_pthread_sb/result.json) | PASS | Sometimes | Sometimes | PASS |
| [P02_atomic_fence](P02_atomic_fence/result.json) | PASS | Never | Never | PASS |
| [P03_release_acquire_relay](P03_release_acquire_relay/result.json) | PASS | Never | Never | PASS |

每个 Case 目录提供 `source.ll`、`eventir.json`、`unit.json`、两架构 litmus、寄存器映射和 herd7 原始日志。
以本次 `result.json` 为准；失败运行不会把既有旧文件认作本次成功证据。
