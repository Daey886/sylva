"""Sylva CLI: 极简命令行入口，桥接三大原语到终端。

用法:
    sylva inject "SQLite FTS5" --session sess_main
    sylva ingest "规则：禁止裸连接" --type rule
    sylva ring --ttl-days 30
    sylva core set developer "木头 (Daey886)"
    sylva core list
    sylva checkpoint set sess_main "上次任务停在..."
    sylva checkpoint get

全局 --db 可指定数据库路径，默认 $SYLVA_HOME/sylva.db。
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sylva.core import SylvaStore
from sylva.primitives import SylvaKernel

app = typer.Typer(
    name="sylva",
    help="Sylva 超精简 Agent 记忆引擎：inject / ingest / ring / core / checkpoint。",
    no_args_is_help=True,
)

# 允许的 ring_type 枚举
RING_TYPES = ("fact", "rule", "decision", "interaction")


def _store(db: Path | None) -> SylvaStore:
    """按 --db 参数构造存储实例（None 时用默认路径）。"""
    return SylvaStore(db) if db else SylvaStore()


def _kernel(db: Path | None) -> SylvaKernel:
    return SylvaKernel(_store(db))


@app.command()
def inject(
    query: Annotated[str, typer.Argument(help="检索关键词，用于召回相关年轮")] = "",
    session: Annotated[
        str | None, typer.Option("--session", "-s", help="断点 session_id")
    ] = None,
    max_chars: Annotated[
        int, typer.Option("--max-chars", "-m", help="上下文硬性字符上限")
    ] = 4000,
    recall_limit: Annotated[
        int, typer.Option("--recall-limit", "-n", help="年轮召回条数")
    ] = 5,
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """请求前组装上下文（Core + Checkpoint + Rings 召回）。"""
    result = _kernel(db).inject(
        query=query, session_id=session, max_chars=max_chars, recall_limit=recall_limit
    )
    typer.echo(result["context"])


@app.command()
def ingest(
    content: Annotated[str, typer.Argument(help="要沉淀的事实/规则/决策/交互内容")],
    ring_type: Annotated[
        str, typer.Option("--type", "-t", help="年轮类型 fact/rule/decision/interaction")
    ] = "fact",
    importance: Annotated[
        float, typer.Option("--importance", "-i", help="权重 0.0~1.0")
    ] = 1.0,
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """原子写入一条年轮（SHA256 幂等防重）。"""
    if ring_type not in RING_TYPES:
        typer.echo(f"错误：ring_type 必须是 {RING_TYPES} 之一", err=True)
        raise typer.Exit(code=2)
    if not 0.0 <= importance <= 1.0:
        typer.echo("错误：importance 必须在 0.0~1.0 之间", err=True)
        raise typer.Exit(code=2)

    written = _kernel(db).ingest(content=content, ring_type=ring_type, importance=importance)
    if written:
        typer.echo(f"✓ 已写入年轮 [{ring_type}]")
    else:
        typer.echo("⊙ 已存在，跳过（内容哈希相同）")


@app.command()
def ring(
    ttl_days: Annotated[
        float, typer.Option("--ttl-days", "-d", help="超期低权重交互年轮保留天数")
    ] = 30.0,
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """整理年轮：衰减清理超期低权重临时交互。"""
    report = _kernel(db).ring_consolidate(ttl_days=ttl_days)
    typer.echo(f"✓ 已整理，衰减清理 {report['decayed_rings']} 条年轮")


core_app = typer.Typer(help="核心记忆（树心）管理。")
app.add_typer(core_app, name="core")


@core_app.command("set")
def core_set(
    key: Annotated[str, typer.Argument(help="核心记忆键")],
    value: Annotated[str, typer.Argument(help="核心记忆内容")],
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """写入/更新一条核心记忆。"""
    _store(db).set_core(key, value)
    typer.echo(f"✓ 已写入核心记忆 [{key}]")


@core_app.command("get")
def core_get(
    key: Annotated[str, typer.Argument(help="核心记忆键")],
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """读取一条核心记忆。"""
    value = _store(db).get_core(key)
    typer.echo(value if value is not None else f"(未找到 [{key}])")


@core_app.command("list")
def core_list(
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """列出所有核心记忆。"""
    cores = _store(db).list_cores()
    if not cores:
        typer.echo("(无核心记忆)")
        return
    for k, v in cores.items():
        typer.echo(f"- {k}: {v}")


checkpoint_app = typer.Typer(help="断点上下文管理。")
app.add_typer(checkpoint_app, name="checkpoint")


@checkpoint_app.command("set")
def checkpoint_set(
    session: Annotated[str, typer.Argument(help="session_id")],
    context: Annotated[str, typer.Argument(help="断点上下文内容")],
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """记录一个断点上下文。"""
    _store(db).set_checkpoint(session, context)
    typer.echo(f"✓ 已记录断点 [{session}]")


@checkpoint_app.command("get")
def checkpoint_get(
    session: Annotated[
        str | None, typer.Argument(help="session_id（缺省取最近一次）")
    ] = None,
    db: Annotated[Path | None, typer.Option("--db", help="数据库路径")] = None,
) -> None:
    """读取断点上下文。"""
    store = _store(db)
    if session:
        ctx = store.get_checkpoint(session)
        typer.echo(ctx if ctx is not None else f"(未找到断点 [{session}])")
    else:
        latest = store.get_latest_checkpoint()
        if latest:
            typer.echo(f"[{latest[0]}]\n{latest[1]}")
        else:
            typer.echo("(无断点记录)")


if __name__ == "__main__":
    app()
