# ADR-001: Sylva 架构设计与微内核规范 (Architecture Decision Record)

- **状态**: 提议中 (Proposed)
- **作者**: Hermes + Daey886
- **日期**: 2026-10-23
- **项目目标**: 打造专属于个人与智能体生态的超轻量 (Ultra-lean) 记忆引擎，单文件 SQLite WAL 物理持久化，零过度设计。

---

## 1. 背景与核心问题 (Context)
过去的智能体外挂记忆系统普遍存在以下致命弊端：
1. **过度设计与包袱沉重**：企业级多租户、多数据库分离、复杂的微服务和多层封装，带来严重的性能损耗与维护心智负担。
2. **死锁与并发崩溃**：多连接争抢 SQLite 锁、连接未规范释放导致锁泄漏、后台常驻呼吸机脚本难以维系。
3. **记忆碎片与幻觉死循环**：无节制的记忆自动注入导致上下文被低价值杂讯撑爆，且存在跨模型记忆隔离与鉴权断点。

## 2. 设计原则 (Principles)
1. **极致精简 (Ponytail Principle)**：
   - 核心纯代码行数严格控制在 **800 行以内**。
   - 零未经验证的第三方重型向量数据库依赖（Milvus/Qdrant/Chroma 统统不要），单机即巅峰。
2. **年轮哲学 (Tree-Ring Philosophy)**：
   - 记忆如树木年轮，不可磨灭、层层物理致密。
   - 记忆分为三层形态：**CoreMemory (树心)**、**Checkpoint (近景断面)**、**Rings (年轮事实)**。
3. **单库 WAL 模式**：
   - 单一 SQLite 物理文件 `~/.sylva/sylva.db`，强制开启 `PRAGMA journal_mode=WAL` 与 `PRAGMA synchronous=NORMAL`。
   - 所有数据库连接统一通过安全 ContextManager 治理，禁止裸连接。

## 3. 三大原子原语 (Core Primitives)

Sylva 对外仅暴露收敛的三大核心原语，彻底杜绝发散：

### 原语一：`inject` (请求前执行)
- **职责**：在宿主智能体执行 LLM 调用前，微秒级检索并装配紧凑上下文。
- **组成**：
  1. `CoreMemory`：常驻核心事实块（用户画像、硬性规则、长期设定）。
  2. `Checkpoint`：上一次工作断点（在跨会话首轮提供平滑续接）。
  3. `Rings Recall`：基于当前 Prompt 的 FTS5 全文 + FastEmbed 紧凑向量双轨混合召回。
- **输出约束**：硬性上下文长度限制（默认 <= 4000 字符），防打爆 LLM 窗口。

### 原语二：`ingest` (请求后执行)
- **职责**：在宿主交互结束或产出关键产物时，原子写入年轮。
- **特性**：
  - 纯异步/无阻塞落盘，不增加交互延迟。
  - 支持幂等写入（Hash 去重防重复投递）。
  - 写入事务原子性（通过 SQLite 事务，写失败快速重试，防半包）。

### 原语三：`ring` (年轮整理 / Consolidate)
- **职责**：后台或闲时自动执行的认知整理。
- **动作**：
  - 事实冲突消解（以新换旧、标记废弃）。
  - 过期临时上下文（TTL）软清理。
  - 碎片化记忆提炼为致密的年轮总结。

## 4. 技术栈选型 (Technology Stack)
- **运行时**: Python 3.10+
- **存储引擎**: SQLite3 (内置 FTS5 全文索引扩展)
- **向量检索**: FastEmbed (轻量 CPU 优化嵌入模型，启动极快，内存占用 <100MB)
- **服务接口**: FastAPI / Uvicorn (轻量 HTTP) + 极速 CLI 接口
- **测试与门禁**: Pytest + Semgrep (静态安全规则网) + GitHub Actions CI

## 5. 目录结构规范 (Directory Structure)
```
sylva/
├── .github/workflows/ci.yml       # 严格的自动化 CI 检查门禁
├── docs/adr/                      # 架构决策记录
├── sylva/
│   ├── __init__.py
│   ├── core.py                    # 微内核：单库 WAL 引擎与连接池
│   ├── search.py                  # 双轨检索：FTS5 + 嵌入向量
│   ├── primitives.py              # 三大原语：inject / ingest / ring
│   ├── api.py                     # 轻量 HTTP 接口服务
│   └── cli.py                     # 本地命令行调用工具
├── tests/                         # 100% 覆盖率的单元测试
├── pyproject.toml                 # 现代化标准包配置
└── README.md
```

## 6. 安全与防御底线 (Security & Gates)
根据 2026-10-22 五路模型审查教训，Sylva 严守以下代码铁律：
1. **禁止 `str(e)` 进外部响应**：所有 API 统一错误出口，禁止泄露内部调用栈。
2. **强制使用连接管理器**：所有游标与连接必须在 `with get_db() as db:` 下执行，严禁裸连接或遗漏 `finally`。
3. **输入严格校验**：所有整数、分页、字符串长度由 Pydantic v2 / 内置函数硬约束。
4. **CI 必须跑通全量测试**：分支合并必须经由 PR、代码审查、CI 全绿。
