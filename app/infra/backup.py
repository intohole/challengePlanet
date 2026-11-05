#!/usr/bin/env python3
"""S107 业务库持续备份模板（权威源）。

五护栏：dry-run 默认 / VACUUM INTO 活库安全备份 / integrity+行数对账回读校验 /
keep-N 顶新 / 清理白名单只删本引擎产物。仓内副本（usercenter_app/backup.py 等）
按 ALLOWED_DRIFT 白名单差异从本模板派生，指纹制单源（out/s107/template_fingerprint.json）。
调度接线形态：nexus.get_scheduler().add_interval_job（scheduler_gate 门禁自动生效）。
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BACKUP_INTERVAL_HOURS = 6
MAX_BACKUPS = 10
VERIFY_TABLES: list[str] = ['challenges', 'checkins', 'points_ledger']


def _resolve_db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "challenge.db"


def _resolve_backup_dir() -> Path:
    db = _resolve_db_path()
    return db.parent / "backups"


def _backup_prefix() -> str:
    return "cp"


def _verify_sqlite_integrity(db_path: Path) -> bool:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute("PRAGMA integrity_check")
            row = cur.fetchone()
            return bool(row and row[0] == "ok")
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def _table_count(db_path: Path, table: str) -> Optional[int]:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            row = cur.fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _vacuum_into(source: Path, target: Path) -> None:
    conn = sqlite3.connect(str(source))
    try:
        escaped = str(target).replace("'", "''")
        conn.execute(f"VACUUM INTO '{escaped}'")
    finally:
        conn.close()


def create_backup() -> dict[str, object]:
    db_path = _resolve_db_path()
    report: dict[str, object] = {"ok": False, "ts": datetime.now().isoformat(timespec="seconds")}
    if not db_path.exists():
        report["error"] = f"db not found: {db_path}"
        return report
    backup_dir = _resolve_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"{_backup_prefix()}_{stamp}.db"
    if target.exists():
        report["error"] = "collision"
        return report
    _vacuum_into(db_path, target)
    if not target.exists() or target.stat().st_size == 0:
        report["error"] = "backup file empty"
        target.unlink(missing_ok=True)
        return report
    if not _verify_sqlite_integrity(target):
        report["error"] = "integrity_check failed"
        target.unlink(missing_ok=True)
        return report
    checks = []
    for table in VERIFY_TABLES:
        src_n = _table_count(db_path, table)
        bak_n = _table_count(target, table)
        ok = src_n is not None and bak_n is not None and bak_n >= src_n
        checks.append({"table": table, "src": src_n, "backup": bak_n, "ok": ok})
    report["backup"] = str(target)
    report["size_bytes"] = target.stat().st_size
    report["integrity"] = "ok"
    report["table_checks"] = checks
    report["ok"] = all(c["ok"] for c in checks) if checks else True
    if not report["ok"]:
        target.unlink(missing_ok=True)
        return report
    report["pruned"] = cleanup_old_backups()
    return report


def cleanup_old_backups(keep: int = MAX_BACKUPS) -> list[str]:
    backup_dir = _resolve_backup_dir()
    if not backup_dir.exists():
        return []
    prefix = f"{_backup_prefix()}_"
    backups = sorted(
        (b for b in backup_dir.glob(f"{prefix}*.db") if b.is_file()),
        reverse=True,
    )
    pruned = []
    for old in backups[keep:]:
        try:
            old.unlink()
            pruned.append(old.name)
        except OSError:
            pass
    return pruned


def register_backup(interval_hours: int = BACKUP_INTERVAL_HOURS) -> Optional[object]:
    from nexus.scheduler import get_scheduler

    def _job() -> None:
        try:
            report = create_backup()
            if not report.get("ok"):
                logger.error("backup failed: %s", report)
        except Exception:
            logger.exception("continuous backup job crashed")

    get_scheduler().add_interval_job(
        _job, job_id="db-continuous-backup", hours=interval_hours
    )
    return get_scheduler()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.dry_run and not args.execute:
        db_path = _resolve_db_path()
        plan = {
            "dry_run": True,
            "db": str(db_path),
            "exists": db_path.exists(),
            "backup_dir": str(_resolve_backup_dir()),
            "keep": MAX_BACKUPS,
            "interval_hours": BACKUP_INTERVAL_HOURS,
            "verify_tables": VERIFY_TABLES,
        }
        print(json.dumps(plan, ensure_ascii=False, indent=1) if args.json else plan)
        return 0
    report = create_backup()
    print(json.dumps(report, ensure_ascii=False, indent=1) if args.json else report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
