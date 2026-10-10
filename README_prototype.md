# 独立并发前端与回归原型

这个原型让三个内部 Case 实际经过 Clang、EventIR、保守切片、litmus 和 herd7。
入口与输出都在本目录中，原有 Team Repo 的受限 C CLI 和 C01–C08 人工 Oracle 保持各自的用途。
这是新建的独立原型，不是团队内部核心前端的替代版本，也没有引入 SVF。

## 一条命令运行

从工作区执行：

```bash
cd /home/zhovy/work/Case_Regression_Internal
bash scripts/run_prototype.sh
```

当前工作区已准备 Clang 18.1.3 和 herd7 7.58。
脚本优先使用工作区 `.tools/clang18/bin/clang`；herd7 可从 PATH 或已安装的 opam switch 发现。
换机器时可执行 `bash scripts/setup_tools.sh` 检查环境；该脚本可在 Ubuntu 24.04 amd64 上将固定版本 Clang 包下载并解压到工作区，不使用 sudo。
它不会代替安装缺失的 herdtools7；缺失时会明确提示。其他平台应提供自己的 Clang。

也可以显式指定工具与模型：

```bash
python3 -m prototype \
  --clang /path/to/clang \
  --herd7 /path/to/herd7 \
  --x86-model /path/to/x86tso.cat \
  --riscv-model /path/to/riscv.cat \
  --out results/prototype
```

单个 Case 可作为位置参数，例如 `python3 -m prototype cases/P02_atomic_fence --clang /path/to/clang`。
使用 `--no-run-herd` 可以只检查抽取和生成；整体状态会保持 `UNKNOWN`，退出码为 2。

## 三个样例

| Case | 检查重点 | 目标结果 | x86-TSO 预期 | RVWMO 预期 |
| --- | --- | --- | --- | --- |
| P01_pthread_sb | pthread 线程发现、普通全局读写、删除单线程 private_noise | 两个 Load 都读到 0 | Sometimes | Sometimes |
| P02_atomic_fence | relaxed 原子读写、seq_cst fence 保留 | 两个 Load 都读到 0 | Never | Never |
| P03_release_acquire_relay | 三线程、helper 调用、release/acquire 传递、Load→Store 值依赖 | 传递成功但 data 仍读到 0 | Never | Never |

每个目录含 `case.c`、手工编写的 `expected.json` 和解释预期的 `expected.md`。
Oracle 在工具输出之前独立编写，回归检查线程、事件种类、对象类型与初值、内存序、写入值、切片保留/删除对象和模型观测。
新增 Case 应沿用这个结构，不能将一次工具输出直接复制为预期。

运行结果见 [results/prototype/summary.md](results/prototype/summary.md) 和机器可读的 `summary.json`。
每个 Case 的结果目录包含：

| 文件 | 内容 |
| --- | --- |
| source.ll | 同一输入经 Clang `-O0 -g -S -emit-llvm` 生成的 LLVM IR，作为检查材料 |
| eventir.json | AST 抽取的线程、全局内存对象、事件、内存序和源码位置 |
| unit.json | may-shared 对象、种子扩展后的 Verification Unit、po/值依赖/潜在通信边和观测条件 |
| x86.litmus / riscv.litmus | 按本原型明确映射规则生成的硬件模型输入 |
| *.registers.json | 事件 ID 到 litmus 观测寄存器的映射 |
| *.herd.txt | 本次实际 herd7 执行的原始输出 |
| result.json | 结构与模型检查状态、错误原因、执行命令、源码/Oracle/LLVM/顶层模型文件哈希 |

`source.ll` 是编译器输出检查材料；当前 EventIR 来自 Clang AST，尚未实现 AST/LLVM 联合分析。
`result.json` 与汇总记录本次运行。遇到失败时，不应把目录内前一次保留的其他文件当成本次成功证据。

## 语义与能力边界

输入限定为单 C11 文件、直线 pthread 创建和 join、每个 worker 运行一次、全局 32 位 int/atomic_int、至多一个 int 参数的直接 helper 调用，以及受支持的原子 Load/Store/Fence。
假设 pthread_create 成功，所有 create 位于所有 join 之前。不会执行输入 C 程序来推断并发结果。

切片以 may-shared 对象为种子，保守扩展参与线程中的其他共享对象，保留同步事件和写入值依赖。
它可以删除 P01 中不影响共享事件的单线程 noise，尚不承诺最小切片或一般并发程序的切片正确性。
跨线程同对象边只表示潜在通信；实际 reads-from 与允许执行由 herd7 模型决定，不能把这些边直接称作 happens-before。

原子操作采用以下硬件映射；模型结论仅针对这个明确映射。

| 源事件 | x86 | RISC-V |
| --- | --- | --- |
| plain/relaxed Load、Store | MOV | LW、SW |
| acquire Load | MOV | LW；FENCE R,RW |
| release Store | MOV | FENCE RW,W；SW |
| seq_cst Load | MOV | FENCE RW,RW；LW；FENCE R,RW |
| seq_cst Store | MOV；MFENCE | FENCE RW,W；SW |
| acquire/release/acq_rel Fence | 不生成硬件指令，保留事件与程序顺序 | FENCE R,RW / RW,W / FENCE.TSO |
| seq_cst Fence | MFENCE | FENCE RW,RW |

映射参考 [RISC-V 官方内存模型说明](https://docs.riscv.org/reference/isa/unpriv/mm-eplan.html) 和 [LLVM 原子操作说明](https://llvm.org/docs/Atomics.html)。
模型分析使用 [herdtools7](https://github.com/herd/herdtools7) 的 x86tso.cat 和 riscv.cat。

P01 普通共享 int 的跨线程访问在 C 语言层存在数据竞争，所以其结果只能作为静态抽取与硬件事件投影的 Oracle。
三个 Case 的 PASS 都不意味着一般 C/C++ 程序正确、任意编译器输出正确或迁移不存在风险。

后续已为 C01–C08 增加直接线程参数、唯一 int 指针别名、单个受保护并初始化的堆分配、全局扁平 int 结构体字段；范围及结构回归入口见 [八例自动回归说明](README_internal_regression.md)。
仍不支持一般指针/别名分析、多个分配点、嵌套结构、任意条件分支、循环、函数指针、RMW/CAS、consume、条件变量或一般锁协议。
直接全局 mutex 的 Lock/Unlock 可记录为事件，但没有硬件 lowering，完整验证返回 UNKNOWN。
P03 的“复杂同步”具体指三线程 release/acquire 传递；不是对任意复杂同步的覆盖。
不支持的可达语法会报告源码位置，不会静默当作已处理。

状态与退出码：PASS/0 表示所有本次结构和模型结果符合 Oracle；FAIL/1 表示存在不匹配；UNKNOWN/2 表示缺少工具、能力不支持或模型没有返回可靠结果。

## 回归测试

```bash
source ../.tools/case-regression-env.sh
python3 -m unittest discover -s tests -v
```

测试包括实际源码抽取、两种模型结果、删除 fence/内存序的对照，以及不支持语法和后端失败时的处理。
工具不可用时，依赖真实工具的测试会明确 skip；完整验证还需要运行上面的三 Case 入口并检查退出码。

后续接入团队前端时，可以沿用 Case 和 Oracle，通过转换接口产出相同结构，逐步替换这个有界抽取器。
