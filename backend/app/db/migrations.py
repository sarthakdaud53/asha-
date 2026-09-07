"""
Lightweight, dependency-free schema migration helper.

SQLAlchemy's Base.metadata.create_all() only creates tables that don't yet
exist — it never alters an existing table when a model gains new columns.
On a long-lived SQLite file (like digital_asha.db) that means the live
database can silently drift behind models.py.

run_migrations() closes that gap for the common case (new nullable columns
with a default) without introducing a full migration framework. It is:
  - Idempotent: safe to call on every startup.
  - Additive only: never drops or renames a column, never touches existing rows.
  - Scoped: only ever runs ALTER TABLE ... ADD COLUMN for columns declared
    in models.py that are missing from the live table.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


# Columns that must exist on each table, and the SQLite-compatible DDL
# fragment to add them if missing. Keep this in sync with models.py.
REQUIRED_COLUMNS = {
    "users": {
        "password_reset_token_hash": "VARCHAR(64)",
        "password_reset_expires_at": "DATETIME",
    },
    "house_visits": {
        "priority": "VARCHAR(20) NOT NULL DEFAULT 'MEDIUM'",
        "completed_at": "DATETIME",
        "notes": "TEXT",
    },
    "notifications": {
        "priority": "VARCHAR(20) NOT NULL DEFAULT 'MEDIUM'",
        "channel": "VARCHAR(30) NOT NULL DEFAULT 'in_app'",
        "link": "VARCHAR(200)",
    },
    "villages": {
        "location_village_id": "INTEGER REFERENCES location_villages(id) ON DELETE RESTRICT",
    },
}


def run_migrations(engine: Engine) -> list[str]:
    """
    Inspects the live database and adds any columns that models.py expects
    but the table is missing. Returns a list of human-readable messages
    describing what (if anything) was changed, for startup logging.
    """
    applied = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, columns in REQUIRED_COLUMNS.items():
            if table_name not in existing_tables:
                # Table doesn't exist yet at all — create_all() will handle
                # it with the full correct schema, nothing to migrate.
                continue

            existing_columns = {
                col["name"] for col in inspector.get_columns(table_name)
            }

            for col_name, ddl in columns.items():
                if col_name in existing_columns:
                    continue
                conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {ddl}")
                )
                msg = f"[MIGRATION] Added missing column {table_name}.{col_name}"
                applied.append(msg)
                print(msg)

    if not applied:
        print("[MIGRATION] Schema already up to date. No changes applied.")

    return applied
