import sqlite3
from pathlib import Path

import pytest

from app.infra import backup


@pytest.fixture()
def fake_env(tmp_path, monkeypatch):
    src = tmp_path / "src.db"
    conn = sqlite3.connect(str(src))
    for table in backup.VERIFY_TABLES:
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany(f"INSERT INTO {table} VALUES (?, ?)", [(i, f"u{i}") for i in range(5)])
    conn.commit()
    conn.close()
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup, "_resolve_db_path", lambda: src)
    monkeypatch.setattr(backup, "_resolve_backup_dir", lambda: backup_dir)
    return src, backup_dir


def test_dry_run_zero_side_effect(fake_env):
    src, backup_dir = fake_env
    assert not backup_dir.exists()
    assert src.exists()


def test_backup_creates_verified_copy(fake_env):
    src, backup_dir = fake_env
    report = backup.create_backup()
    assert report["ok"] is True
    assert report["integrity"] == "ok"
    table = backup.VERIFY_TABLES[0]
    assert backup._table_count(src, table) == 5
    assert backup._table_count(Path(str(report["backup"])), table) == 5


def test_backup_missing_db_returns_error(fake_env, monkeypatch):
    monkeypatch.setattr(backup, "_resolve_db_path", lambda: Path("/nonexistent/x.db"))
    report = backup.create_backup()
    assert report["ok"] is False


def test_keep_n_prunes_oldest(fake_env):
    src, backup_dir = fake_env
    backup_dir.mkdir(parents=True)
    for i in range(12):
        f = backup_dir / f"{backup._backup_prefix()}_20260101_0000{i:02d}.db"
        f.write_bytes(b"x")
    newest = backup_dir / f"{backup._backup_prefix()}_20260202_020202.db"
    newest.write_bytes(b"x")
    pruned = backup.cleanup_old_backups(keep=10)
    remaining = sorted(p.name for p in backup_dir.glob(f"{backup._backup_prefix()}_*.db"))
    assert len(remaining) == 10
    assert remaining[-1] == newest.name
    assert len(pruned) == 3


def test_cleanup_whitelist_never_touches_foreign_files(fake_env):
    src, backup_dir = fake_env
    backup_dir.mkdir(parents=True)
    foreign = backup_dir / "important_notes.txt"
    foreign.write_text("keep me")
    stranger = backup_dir / "other_engine_20260101.db"
    stranger.write_bytes(b"y")
    backup.cleanup_old_backups(keep=0)
    assert foreign.exists()
    assert stranger.exists()
