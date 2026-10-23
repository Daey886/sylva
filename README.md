# Sylva (西尔瓦) 🌲

> **Ultra-lean agent memory engine with SQLite WAL and tree-ring consolidation.**  
> 专为大模型与智能体生态打造的超轻量自研记忆引擎。年轮沉淀，木木相生。

---

## 核心设计理念

1. **极致精简 (Ultra-Lean)**：核心逻辑控制在 800 行以内，杜绝冗余抽象与过度设计。
2. **年轮哲学 (Tree-Ring Philosophy)**：
   - 记忆如树木年轮般致密沉淀，拒绝浮肿与上下文杂讯污染。
   - 三大极简原语：`inject`（请求前注入）、`ingest`（原子写入）、`ring`（年轮整理）。
3. **单库 WAL 模式**：
   - 基于单一 SQLite 物理文件，开启 WAL 模式并发治理。
   - 内置 FTS5 全文索引 + FastEmbed 极小向量模型，双轨精准召回。

## 架构决策与规范
详见 [ADR-001: Sylva 架构设计与微内核规范](docs/adr/ADR-001-microkernel-architecture.md)。

## License
MIT License © 2026 Daey886
