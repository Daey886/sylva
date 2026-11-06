# Nowledge Mem 架构解构与 Sylva 演进落地方案

> 日期：2026-10-26  
> 评测来源：Nowledge Mem (mem.nowledge.co) 外部架构拆解  
> 状态：落地规约化进行中  

## 1. 外部架构核心精粹

Nowledge Mem 提炼出的三大工业级设计，针对大模型记忆系统在实际工程中的致命软肋：

### 机制一：上下文压缩前转录本原子抢救（Pre-Compaction Transcript Flush）
- **痛点**：长会话在触发 LLM `/compress` 压缩时，模型摘要通常会抹平具体的代码细节、错误堆栈、物理参数。
- **解法**：在触发压缩前夕，系统强制执行物理快照，将未归档的关键代码、命令输出与错误堆栈直接转录并持久化落盘至底层年轮（Rings），确保摘要压缩后依然能够通过高精度回溯调取现场。

### 机制二：技能调用成败结构化特征提取（Skill Outcome Extractor）
- **痛点**：记忆系统仅记录自然语言对话，缺乏对执行层工具（Tools / Skills）的健壮度感知。
- **解法**：不扫描自由文本，仅针对结构化工具调用返回的 `(tool_name, exit_code, status, latency)` 进行自动化统计，挂钩胜率并构建量化判决基准。

### 机制三：决策演变三层证据链（Versioning Graph Traceability）
- **痛点**：记忆覆盖通常简单粗暴替换旧认知，导致决策背景与演化动机丢失。
- **解法**：建立 `记忆切片 -> 原会话快照 -> 原始文档` 的三层有向图谱，保留 `v1 -> v2 -> v3` 的演变脉络，使每次信念修正具备完整的历史因果依据。

---

## 2. Sylva 本土化融合与落地矩阵

结合 Sylva 现有的微内核设计（`rings`, `core_memory`, `relations`, `mental_models`），规划三大本土化落地动作：

| 机制 | 目标模块 | 实现方式 | 阶段 |
| :--- | :--- | :--- | :--- |
| **原子抢救** | `sylva/primitives.py` & Agent Hooks | 新增 `flush_pre_compaction` API，在压缩事件前将最近一轮未归档的 terminal/file 快照作为 `type=snapshot` 年轮落盘 | Phase 8 |
| **技能成败提取** | `sylva/core.py` (`tool_metrics` 表) | 记录工具调用的成功/失败/耗时，为 Agent 规划提供避坑基准 | Phase 9 |
| **三层演变图谱** | `sylva/relations.py` & `mental_models` | Mental Model / Core 更新时，显式在 relations 表中记录 `supersedes` 边及 `reason` | Phase 10 |
