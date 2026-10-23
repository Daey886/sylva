"""CLI 命令层测试：覆盖 inject / ingest / ring / core / checkpoint。"""

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from sylva.cli import app

runner = CliRunner()


def _db(tmpdir: str) -> str:
    return str(Path(tmpdir) / "cli_test.db")


def test_ingest_then_inject_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _db(tmpdir)

        r = runner.invoke(app, ["ingest", "用户拒绝使用重型向量数据库", "--db", db, "--type", "fact"])
        assert r.exit_code == 0, r.output
        assert "已写入年轮" in r.output

        r = runner.invoke(app, ["inject", "向量数据库", "--db", db])
        assert r.exit_code == 0, r.output
        assert "向量数据库" in r.output


def test_ingest_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _db(tmpdir)
        args = ["ingest", "同一内容", "--db", db, "--type", "fact"]

        r1 = runner.invoke(app, args)
        assert "已写入年轮" in r1.output

        r2 = runner.invoke(app, args)
        assert "已存在" in r2.output


def test_ingest_rejects_bad_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _db(tmpdir)
        r = runner.invoke(app, ["ingest", "内容", "--db", db, "--type", "bogus"])
        assert r.exit_code == 2
        assert "错误" in r.output


def test_core_set_get_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _db(tmpdir)

        r = runner.invoke(app, ["core", "set", "developer", "木头", "--db", db])
        assert r.exit_code == 0

        r = runner.invoke(app, ["core", "get", "developer", "--db", db])
        assert "木头" in r.output

        r = runner.invoke(app, ["core", "list", "--db", db])
        assert "developer" in r.output


def test_checkpoint_set_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _db(tmpdir)

        r = runner.invoke(app, ["checkpoint", "set", "sess_a", "上次写到一半", "--db", db])
        assert r.exit_code == 0

        r = runner.invoke(app, ["checkpoint", "get", "sess_a", "--db", db])
        assert "上次写到一半" in r.output

        r = runner.invoke(app, ["checkpoint", "get", "--db", db])
        assert "sess_a" in r.output


def test_ring_runs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _db(tmpdir)
        runner.invoke(app, ["ingest", "临时交互", "--db", db, "--type", "interaction", "--importance", "0.1"])
        r = runner.invoke(app, ["ring", "--db", db, "--ttl-days", "0"])
        assert r.exit_code == 0, r.output
        assert "已整理" in r.output
