# 内部 Case 草案

本目录依据《Case_Regression_新成员交接文档_20260918_更新版》建立，**不属于准公开 Team Repo**。这里的 C 文件用于前端静态抽取和自动回归，不执行原始 C 程序来推断并发结果。普通变量跨线程读写可能构成 C 语言层的数据竞争。

- `case_format.md`：每个 Case 的记录格式与状态口径。
- `case_matrix.md`：当前 8 个 Case 的覆盖维度与结构/模型状态。
- `cases/Cxx_*/case.c`：输入源码。
- `cases/Cxx_*/expected.md`：独立于工具输出写出的人工预期。
- `cases/Cxx_*/expected.json`：人工预期的机器可读版本，用于逐字段比较。

当前 Team Repo 的 CLI 仍是受限 C 链路。本目录的独立前端已将八个原始 Case 接入自动结构回归，结果不能视作团队核心前端已完成集成。

## 八个内部 Case 的自动回归

运行 `bash scripts/run_internal_regression.sh`，比较共享对象、事件、切片保留/删除、Verification Unit 和参数/别名/调用关系。
完整输出格式与外部前端接入方式见 [自动回归说明](README_internal_regression.md)，实际结果见 [八例结果表](results/internal/summary.md)。
结构结果与硬件模型结果分别记录；这八例尚无经过审查的模型 Oracle，模型状态保持 UNKNOWN。

## 独立原型与三类完整示例

本目录新增独立的 `prototype/`，使用 Clang AST 抽取有界 pthread/Atomic/Fence 输入，并实际运行 x86-TSO/RVWMO 模型。
P01–P03 分别覆盖普通 pthread、Atomic/Fence 和三线程 release/acquire 传递；人工 Oracle 与原有 C01–C08 分开维护。

运行 `bash scripts/run_prototype.sh`。安装说明、输出解释和能力边界见 [独立原型说明](README_prototype.md)，最近运行结果见 [原型回归结果](results/prototype/summary.md)。
