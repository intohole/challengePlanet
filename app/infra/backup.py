#!/usr/bin/env python3
"""业务库持续备份（S107 五护栏）：行为单源 nexus.backup（r190 收归），本模块仅仓内配置面."""

import logging
from pathlib import Path
from typing import Optional

from nexus.backup import backup_cli, prune_backups, run_backup, table_count

logger = logging.getLogger(__name__)

BACKUP_INTERVAL_HOURS = 6
MAX_BACKUPS = 10
VERIFY_TABLES: list[str] = ['challenges', 'checkins', 'points_ledger']
_table_count = table_count


def _resolve_db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "challenge.db"

def _resolve_backup_dir() -> Path:
    db = _resolve_db_path()
    return db.parent / "backups"

def _backup_prefix() -> str:
    return "cp"


def create_backup() -> dict[str, object]:
    return run_backup(
        _resolve_db_path(),
        _resolve_backup_dir(),
        _backup_prefix(),
        VERIFY_TABLES,
        keep=MAX_BACKUPS,
    )


def cleanup_old_backups(keep: int = MAX_BACKUPS) -> list[str]:
    return prune_backups(_resolve_backup_dir(), _backup_prefix(), keep)


def register_backup(interval_hours: int = BACKUP_INTERVAL_HOURS) -> Optional[object]:
    from nexus.backup import register_backup_job

    return register_backup_job(
        _resolve_db_path(),
        _resolve_backup_dir(),
        _backup_prefix(),
        VERIFY_TABLES,
        keep=MAX_BACKUPS,
        interval_hours=interval_hours,
    )


def main() -> int:
    return backup_cli(
        _resolve_db_path,
        _resolve_backup_dir,
        _backup_prefix,
        VERIFY_TABLES,
        keep=MAX_BACKUPS,
        interval_hours=BACKUP_INTERVAL_HOURS,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main())
