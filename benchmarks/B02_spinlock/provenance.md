# B02：来源、许可与适配记录

## 上游来源与许可

来源为 [DPDK/dpdk](https://github.com/DPDK/dpdk)，v24.11，提交 `1b3bf1128d9bda5595861814792f74b8f57160c8`。

[generic/rte_spinlock.h](https://github.com/DPDK/dpdk/blob/1b3bf1128d9bda5595861814792f74b8f57160c8/lib/eal/include/generic/rte_spinlock.h)提供锁类型、init、lock、unlock 和 trylock。

[generic/rte_pause.h](https://github.com/DPDK/dpdk/blob/1b3bf1128d9bda5595861814792f74b8f57160c8/lib/eal/include/generic/rte_pause.h)提供 32 位等待函数；`rte_stdatomic.h` 提供原始 C11 原子接口。

原始完整文件、下载地址与 SHA256 保存在 ../vendor/dpdk/ 和 ../vendor/manifest.json；原样保留 Intel、Cavium、Arm、Microsoft 等版权及 BSD-3-Clause 许可。

## 核心实现提取

`common/dpdk_spinlock.h` 按固定文本区间提取类型、初始化、获取、释放和 trylock；`common/dpdk_wait.h` 提取 32 位等待函数。函数体不修改。

`python3 ../scripts/check_sources.py` 校验来源哈希和提取文本；`--write-extracts` 从已校验来源重建。

RTE_FORCE_INTRINSICS 和 RTE_ENABLE_STDATOMIC 选择上游通用 C11 路径，保留 CAS 内存序、expected 重置、等待条件和 release 解锁。

## 外围适配

不提取递归锁和硬件事务锁接口，去除相应 lcore/EAL 依赖；这些不属于本例协议。

`common/platform.h` 提供静态注解宏、内联提示和暂停实现，直接包含原始 `rte_stdatomic.h`。等待保留上游对应 signed/unsigned 访问约定，并断言 int 为 32 位。

暂停在 x86 使用 pause、AArch64 使用 yield，其他平台回退为 relaxed signal fence；计数为线程局部统计，不增加线程间同步。

## 本地新增部分

共享 count/checksum、pthread 生命周期、CLI、调度让步及检查逻辑均由本项目补充，不冒充上游某个业务模块。

两个 worker 调用真实 lock/unlock 并执行多轮计算写入；只有 model 下的交接事件投影省略失败重试。

校验损坏控制为人工构造，全部访问仍由同一把锁保护，不代表上游存在已知缺陷。

可选更新轨迹由各 worker 独占缓冲，持锁复制 update_record 前后实际值，join 后导出；上游 CAS、等待和释放函数体不改。记录影响持锁时间及调度，不用于性能比较；Python 检查不调用 C 的 checksum 函数。

`scripts/spinlock_protocol.py` 是本项目手工映射的有限 SC 协议模型，CAS 拆分和遗漏重置只存在于模型变体；测试中间 checksum 错误只修改临时副本。三者都不冒充上游历史缺陷或已证明等价的完整 C11 模型。

复核重点是函数体一致性、原子语义和记录访问的锁保护范围；构建适配和新增驱动均可单独追溯。
