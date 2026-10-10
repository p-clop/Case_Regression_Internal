# C01–C08 自动结构回归

本次结构结果：**PASS**；PASS 8 / FAIL 0 / UNKNOWN 0。

模型验证均为 **UNKNOWN**：这八个 Case 尚无经过审查的架构模型 Oracle。结构 PASS 不代表模型验证通过。

| Case | 共享对象 | 事件 | 切片 | Verification Unit | 绑定/调用 | 保留/删除事件 | 结构结果 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [C01_global](C01_global/result.json) | PASS | PASS | PASS | PASS | PASS | 2/0 | PASS |
| [C02_thread_argument](C02_thread_argument/result.json) | PASS | PASS | PASS | PASS | PASS | 2/0 | PASS |
| [C03_heap_escape](C03_heap_escape/result.json) | PASS | PASS | PASS | PASS | PASS | 2/0 | PASS |
| [C04_struct_fields](C04_struct_fields/result.json) | PASS | PASS | PASS | PASS | PASS | 4/0 | PASS |
| [C05_pointer_alias](C05_pointer_alias/result.json) | PASS | PASS | PASS | PASS | PASS | 2/0 | PASS |
| [C06_helper_function](C06_helper_function/result.json) | PASS | PASS | PASS | PASS | PASS | 2/0 | PASS |
| [C07_two_objects](C07_two_objects/result.json) | PASS | PASS | PASS | PASS | PASS | 4/0 | PASS |
| [C08_unrelated_code](C08_unrelated_code/result.json) | PASS | PASS | PASS | PASS | PASS | 4/1 | PASS |

额外的单元等价检查：
- C08_unrelated_code 与 C07_two_objects：PASS

完整记录：`summary.json`；可导入表格的结果：`summary.csv`。
