# B01：来源、许可与适配记录

## 来源与许可

来源为 [DPDK/dpdk](https://github.com/DPDK/dpdk)，标签 v24.11，提交 `1b3bf1128d9bda5595861814792f74b8f57160c8`。

[rte_ring_elem_pvt.h](https://github.com/DPDK/dpdk/blob/1b3bf1128d9bda5595861814792f74b8f57160c8/lib/ring/rte_ring_elem_pvt.h)提供完整元素操作函数链，[rte_ring_c11_pvt.h](https://github.com/DPDK/dpdk/blob/1b3bf1128d9bda5595861814792f74b8f57160c8/lib/ring/rte_ring_c11_pvt.h)提供 head 预留和 tail 发布。

原始文件、结构体定义、原子接口及 BSD-3-Clause 许可保存在 ../vendor/dpdk/；版权声明保留。下载 URL、原路径和 SHA256 见 ../vendor/manifest.json。在线系列文档会更新，源码以固定提交为准。

## 原始算法与编译路径

`rte_ring_elem_pvt.h`、`rte_ring_c11_pvt.h`、`rte_stdatomic.h` 原样参与编译；`python3 ../scripts/check_sources.py` 检查全部原始哈希。

本地 enqueue/dequeue 仅向内部函数传入 8 字节元素、is_sp/is_sc=1 和批量参数；容量检查、head 更新、复制循环、环绕和发布都由原始函数执行。

RTE_ENABLE_STDATOMIC、RTE_USE_C11_MEM_MODEL 选择上游已有 C11 分支。原始 head 赋值也保留，未改动其原子语义。

## 构建适配

`common/dpdk_ring.h` 保留 size/mask/capacity、四个原子 head/tail 和元素表对齐，删除名称、EAL/memzone、注册、socket、缓存行填充及其他同步模式元数据，使用 calloc 分配连续内存。

该缩减布局不提供完整 DPDK ABI，不用于缓存或吞吐量比较。原始 `rte_ring_core.h` 随包保存用于字段核对。

`common/platform.h` 提供内联、分支提示、注解宏、复制类型及 fence 的 C11 转接。8 字节复制是本例实际路径，16 字节类型仅用于编译未选中函数，不宣称已覆盖。

等待函数从上游机械提取。暂停使用 x86 pause／AArch64 yield，其他平台回退为 relaxed signal fence；暂停次数是线程局部统计，不添加跨线程排序。

## 本地驱动与抽象

pthread 生命周期、启动门、载荷、CLI、统计、断言和顺序边界检查均为本项目新增，不冒充上游业务应用。

主输入保留两个线程、真实数组、运行时写值及多轮复用；只有 model 下的事件投影做了有限抽象。

载荷损坏控制与 relaxed 模型均为人工构造，不代表上游存在已知缺陷。

可选消费记录由本地驱动补充：消费者把私有 data[8] 的值写入独占缓冲，main 在 join 后以 JSONL 导出；不修改上游复制、head/tail 或同步算法。记录增加局部内存写和内存占用，可能改变调度，不用于性能比较。

Python 独立判据位于 `scripts/fifo_oracle.py`，不调用 C 的 message()；双方共用编码函数出错的对照仅在回归测试临时副本中构造，不属于原始输入或上游历史缺陷。

复核时检查来源哈希、共享字段和实际函数链，并区分原始算法、构建适配与新增工作负载。
