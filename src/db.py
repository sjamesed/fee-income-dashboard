"""SQLite database operations for fee income data."""

import re
import sqlite3
from pathlib import Path


class FeeIncomeDB:
    def __init__(self, db_path: str = "data/fee_income.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fee_income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot TEXT NOT NULL,
                platform TEXT NOT NULL,
                project_name TEXT NOT NULL,
                project_status TEXT,
                risk_category TEXT,
                fee_type TEXT NOT NULL,
                period_type TEXT NOT NULL,
                period TEXT NOT NULL,
                amount_usd REAL NOT NULL DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_fee_income_unique
            ON fee_income (snapshot, platform, project_name, fee_type, period_type, period)
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshot ON fee_income (snapshot)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_period ON fee_income (period_type, period)")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS variance_drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot TEXT NOT NULL,
                table_type TEXT NOT NULL,
                project_name TEXT NOT NULL,
                driver_text TEXT DEFAULT '',
                UNIQUE(snapshot, table_type, project_name)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS watch_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                pnl_item TEXT DEFAULT '',
                fund_project TEXT NOT NULL,
                impact_mil REAL,
                lost_delay TEXT,
                comment TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS todo_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot TEXT NOT NULL,
                content TEXT DEFAULT '',
                UNIQUE(snapshot)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshot_meta (
                snapshot TEXT PRIMARY KEY,
                filename TEXT DEFAULT '',
                uploaded_at TEXT DEFAULT ''
            )
        """)
        self.conn.commit()

    def get_todo(self, snapshot: str) -> str:
        rows = self.query("SELECT content FROM todo_notes WHERE snapshot = ?", (snapshot,))
        return rows[0]["content"] if rows else ""

    def save_todo(self, snapshot: str, content: str):
        self.conn.execute(
            "INSERT INTO todo_notes (snapshot, content) VALUES (?, ?) ON CONFLICT(snapshot) DO UPDATE SET content = ?",
            (snapshot, content, content))
        self.conn.commit()

    def save_snapshot_meta(self, snapshot: str, filename: str):
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.conn.execute(
            "INSERT INTO snapshot_meta (snapshot, filename, uploaded_at) VALUES (?, ?, ?) "
            "ON CONFLICT(snapshot) DO UPDATE SET filename = ?, uploaded_at = ?",
            (snapshot, filename, now, filename, now))
        self.conn.commit()

    def get_snapshot_meta(self, snapshot: str) -> dict | None:
        rows = self.query("SELECT * FROM snapshot_meta WHERE snapshot = ?", (snapshot,))
        return rows[0] if rows else None

    def insert_snapshot(self, snapshot: str, rows: list[dict]):
        try:
            self.conn.execute("BEGIN")
            self.conn.execute("DELETE FROM fee_income WHERE snapshot = ?", (snapshot,))
            self.conn.executemany(
                """INSERT INTO fee_income
                   (snapshot, platform, project_name, project_status, risk_category,
                    fee_type, period_type, period, amount_usd)
                   VALUES (:snapshot, :platform, :project_name, :project_status,
                           :risk_category, :fee_type, :period_type, :period, :amount_usd)""",
                rows,
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def list_snapshots(self) -> list[str]:
        rows = self.query("SELECT DISTINCT snapshot FROM fee_income ORDER BY snapshot")
        return [r["snapshot"] for r in rows]

    def delete_snapshot(self, snapshot: str):
        self.conn.execute("DELETE FROM fee_income WHERE snapshot = ?", (snapshot,))
        self.conn.execute("DELETE FROM variance_drivers WHERE snapshot = ?", (snapshot,))
        self.conn.execute("DELETE FROM todo_notes WHERE snapshot = ?", (snapshot,))
        self.conn.execute("DELETE FROM snapshot_meta WHERE snapshot = ?", (snapshot,))
        self.conn.commit()

    def rename_snapshot(self, old_name: str, new_name: str):
        self.conn.execute("UPDATE fee_income SET snapshot = ? WHERE snapshot = ?", (new_name, old_name))
        self.conn.execute("UPDATE variance_drivers SET snapshot = ? WHERE snapshot = ?", (new_name, old_name))
        self.conn.execute("UPDATE todo_notes SET snapshot = ? WHERE snapshot = ?", (new_name, old_name))
        self.conn.execute("UPDATE snapshot_meta SET snapshot = ? WHERE snapshot = ?", (new_name, old_name))
        self.conn.commit()

    def get_latest_snapshot(self) -> str | None:
        snapshots = self.list_snapshots()
        if not snapshots:
            return None
        def _snap_n(s):
            m = re.search(r"(\d+)\+\d+", s)
            return int(m.group(1)) if m else 0
        return max(snapshots, key=_snap_n)

    def get_drivers(self, snapshot: str, table_type: str) -> dict[str, str]:
        """Return {project_name: driver_text} for a given snapshot and table type."""
        rows = self.query(
            "SELECT project_name, driver_text FROM variance_drivers WHERE snapshot = ? AND table_type = ?",
            (snapshot, table_type),
        )
        return {r["project_name"]: r["driver_text"] for r in rows}

    def save_drivers(self, snapshot: str, table_type: str, drivers: dict[str, str]):
        """Save variance drivers (delete + insert)."""
        self.conn.execute(
            "DELETE FROM variance_drivers WHERE snapshot = ? AND table_type = ?",
            (snapshot, table_type))
        for project_name, text in drivers.items():
            self.conn.execute(
                """INSERT INTO variance_drivers (snapshot, table_type, project_name, driver_text)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(snapshot, table_type, project_name) DO UPDATE SET driver_text = ?""",
                (snapshot, table_type, project_name, text, text),
            )
        self.conn.commit()

    def get_watch_list(self) -> list[dict]:
        return self.query("SELECT * FROM watch_list ORDER BY id")

    def update_watch_list(self, items: list[dict]):
        self.conn.execute("DELETE FROM watch_list")
        for item in items:
            self.conn.execute(
                "INSERT INTO watch_list (category, pnl_item, fund_project, impact_mil, lost_delay, comment) VALUES (?, ?, ?, ?, ?, ?)",
                (item["category"], item.get("pnl_item", ""), item["fund_project"],
                 item.get("impact_mil"), item.get("lost_delay"), item.get("comment"))
            )
        self.conn.commit()

    def close(self):
        self.conn.close()
