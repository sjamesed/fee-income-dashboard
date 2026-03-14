"""SQLite database operations for fee income data."""

import sqlite3
from pathlib import Path


class FeeIncomeDB:
    def __init__(self, db_path: str = "data/fee_income.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
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
        return max(snapshots, key=lambda s: int(s.split("+")[0]))

    def close(self):
        self.conn.close()
