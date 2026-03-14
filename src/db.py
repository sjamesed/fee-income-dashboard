"""SQLite database operations for fee income data."""

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
        self.conn.commit()

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
        self.conn.commit()

    def get_latest_snapshot(self) -> str | None:
        snapshots = self.list_snapshots()
        if not snapshots:
            return None
        import re
        def sort_key(s):
            m = re.search(r"(\d+)\+\d+", s)
            return int(m.group(1)) if m else 0
        return max(snapshots, key=sort_key)

    def get_drivers(self, snapshot: str, table_type: str) -> dict[str, str]:
        """Return {project_name: driver_text} for a given snapshot and table type."""
        rows = self.query(
            "SELECT project_name, driver_text FROM variance_drivers WHERE snapshot = ? AND table_type = ?",
            (snapshot, table_type),
        )
        return {r["project_name"]: r["driver_text"] for r in rows}

    def save_drivers(self, snapshot: str, table_type: str, drivers: dict[str, str]):
        """Save variance drivers (upsert)."""
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
