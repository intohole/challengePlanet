#!/usr/bin/env python3
"""业务库备份配置面（r228 BackupShim 收归）：本模块仅声明参数，行为单源 nexus.backup_shim."""

from pathlib import Path

from nexus.backup_shim import BackupShim

BACKUP_INTERVAL_HOURS = 6
MAX_BACKUPS = 10
VERIFY_TABLES: list[str] = ['challenges', 'checkins', 'points_ledger']

shim = BackupShim(
    db_paths=Path(__file__).resolve().parents[2] / "data" / "challenge.db",
    prefix="cp",
    verify_tables=VERIFY_TABLES,
    keep=MAX_BACKUPS,
    interval_hours=BACKUP_INTERVAL_HOURS,
)

register_backup = shim.register_backup
create_backup = shim.create_backup
cleanup_old_backups = shim.cleanup_old_backups
main = shim.main
_resolve_db_path = shim.resolve_db_paths
_resolve_backup_dir = shim.resolve_backup_dir
_backup_prefix = shim.resolve_prefix
if __name__ == "__main__":
    import sys

    sys.exit(main())
