import os
import sqlite3
import pytest
from src.db import FeeIncomeDB

TEST_DB = "data/test_fee_income.db"


@pytest.fixture
def db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    database = FeeIncomeDB(TEST_DB)
    database.init_db()
    yield database
    database.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_init_creates_table(db):
    cursor = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fee_income'"
    )
    assert cursor.fetchone() is not None


def test_insert_and_query(db):
    rows = [
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Bucheon LP",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
         "amount_usd": 100000.0}
    ]
    db.insert_snapshot("2+10", rows)
    result = db.query("SELECT * FROM fee_income WHERE snapshot='2+10'")
    assert len(result) == 1
    assert result[0]["amount_usd"] == 100000.0


def test_upsert_replaces_snapshot(db):
    rows_v1 = [
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Bucheon LP",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
         "amount_usd": 100000.0}
    ]
    rows_v2 = [
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Bucheon LP",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
         "amount_usd": 200000.0}
    ]
    db.insert_snapshot("2+10", rows_v1)
    db.insert_snapshot("2+10", rows_v2)
    result = db.query("SELECT * FROM fee_income WHERE snapshot='2+10'")
    assert len(result) == 1
    assert result[0]["amount_usd"] == 200000.0


def test_list_snapshots(db):
    rows_a = [{"snapshot": "2+10", "platform": "Core Fund", "project_name": "Test",
               "project_status": "Existing", "risk_category": "Committed",
               "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
               "amount_usd": 100.0}]
    rows_b = [{"snapshot": "3+9", "platform": "Core Fund", "project_name": "Test",
               "project_status": "Existing", "risk_category": "Committed",
               "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
               "amount_usd": 200.0}]
    db.insert_snapshot("2+10", rows_a)
    db.insert_snapshot("3+9", rows_b)
    snapshots = db.list_snapshots()
    assert "3+9" in snapshots
    assert "2+10" in snapshots


def test_delete_snapshot(db):
    rows = [{"snapshot": "2+10", "platform": "Core Fund", "project_name": "Test",
             "project_status": "Existing", "risk_category": "Committed",
             "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
             "amount_usd": 100.0}]
    db.insert_snapshot("2+10", rows)
    db.delete_snapshot("2+10")
    result = db.query("SELECT * FROM fee_income WHERE snapshot='2+10'")
    assert len(result) == 0


def test_transaction_rollback_on_failure(db):
    good_rows = [{"snapshot": "2+10", "platform": "Core Fund", "project_name": "Test",
                  "project_status": "Existing", "risk_category": "Committed",
                  "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
                  "amount_usd": 100.0}]
    db.insert_snapshot("2+10", good_rows)
    bad_rows = [{"snapshot": "2+10", "platform": None, "project_name": "Test",
                 "project_status": "Existing", "risk_category": "Committed",
                 "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
                 "amount_usd": 999.0}]
    with pytest.raises(Exception):
        db.insert_snapshot("2+10", bad_rows)
    result = db.query("SELECT * FROM fee_income WHERE snapshot='2+10'")
    assert len(result) == 1
    assert result[0]["amount_usd"] == 100.0
