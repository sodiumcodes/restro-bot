"""CLI script to execute data retention cleanup."""
import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database.connection import SessionLocal
from app.services.retention_service import cleanup_retention


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge expired data per retention policy.")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without deleting.")
    parser.add_argument("--days", type=int, default=None, help="Retention period in days.")
    args = parser.parse_args()

    mode = "DRY RUN: Scanning" if args.dry_run else "Executing"
    print(f"[{mode}] retention cleanup...")

    with SessionLocal() as db:
        counts = cleanup_retention(db=db, days=args.days, dry_run=args.dry_run)

    for entity, count in counts.items():
        print(f"  - {entity}: {count}")

    action = "would be deleted/anonymized" if args.dry_run else "purged/anonymized"
    print(f"Cleanup finished: records {action} successfully.")


if __name__ == "__main__":
    main()
