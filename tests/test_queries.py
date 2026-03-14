import os
import pytest
from src.db import FeeIncomeDB
from src.queries import (
    get_fee_by_project_fy,
    get_fee_by_platform_fy,
    get_ytd_comparison,
    get_fy_comparison,
    get_yoy_comparison,
    get_prior_snapshot_comparison,
    get_snapshot_n_value,
    get_mtd_comparison,
    sort_by_platform,
    PLATFORM_ORDER,
)

TEST_DB = "data/test_queries.db"


@pytest.fixture
def db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    database = FeeIncomeDB(TEST_DB)
    database.init_db()
    rows = [
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-01",
         "amount_usd": 1000000.0},
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "2026-02",
         "amount_usd": 1500000.0},
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "budget", "period": "2026-01",
         "amount_usd": 1200000.0},
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "budget", "period": "2026-02",
         "amount_usd": 1300000.0},
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "forecast", "period": "FY26",
         "amount_usd": 15000000.0},
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "budget", "period": "FY26",
         "amount_usd": 14000000.0},
        {"snapshot": "2+10", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "actual", "period": "FY25",
         "amount_usd": 12000000.0},
        {"snapshot": "2+10", "platform": "Dev JV1", "project_name": "Project B",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Leasing Fee", "period_type": "actual", "period": "2026-01",
         "amount_usd": 500000.0},
        {"snapshot": "2+10", "platform": "Dev JV1", "project_name": "Project B",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Leasing Fee", "period_type": "actual", "period": "2026-02",
         "amount_usd": 600000.0},
        {"snapshot": "2+10", "platform": "Dev JV1", "project_name": "Project B",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Leasing Fee", "period_type": "budget", "period": "2026-01",
         "amount_usd": 400000.0},
        {"snapshot": "2+10", "platform": "Dev JV1", "project_name": "Project B",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Leasing Fee", "period_type": "budget", "period": "2026-02",
         "amount_usd": 450000.0},
        {"snapshot": "2+10", "platform": "Dev JV1", "project_name": "Project B",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Leasing Fee", "period_type": "forecast", "period": "FY26",
         "amount_usd": 7000000.0},
        {"snapshot": "2+10", "platform": "Dev JV1", "project_name": "Project B",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Leasing Fee", "period_type": "budget", "period": "FY26",
         "amount_usd": 6000000.0},
    ]
    database.insert_snapshot("2+10", rows)
    yield database
    database.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_get_snapshot_n_value():
    assert get_snapshot_n_value("2+10") == 2
    assert get_snapshot_n_value("12+0") == 12

def test_ytd_comparison(db):
    result = get_ytd_comparison(db, "2+10")
    assert len(result) == 2
    proj_a = [r for r in result if r["project_name"] == "Project A"][0]
    assert abs(proj_a["ytd_act"] - 2500000.0) < 1
    assert abs(proj_a["ytd_bud"] - 2500000.0) < 1

def test_fy_comparison(db):
    result = get_fy_comparison(db, "2+10")
    assert len(result) == 2
    proj_a = [r for r in result if r["project_name"] == "Project A"][0]
    assert abs(proj_a["fy_fcst"] - 15000000.0) < 1
    assert abs(proj_a["fy_bud"] - 14000000.0) < 1

def test_fee_by_project_fy(db):
    result = get_fee_by_project_fy(db, "2+10")
    assert len(result) == 2
    proj_a = [r for r in result if r["project_name"] == "Project A"][0]
    assert abs(proj_a["fy26_bud"] - 14000000.0) < 1
    assert abs(proj_a["fy26_fcst"] - 15000000.0) < 1

def test_fee_by_platform_fy(db):
    result = get_fee_by_platform_fy(db, "2+10")
    assert len(result) == 2
    core = [r for r in result if r["platform"] == "Core Fund"][0]
    assert abs(core["fy26_bud"] - 14000000.0) < 1

def test_yoy_comparison(db):
    result = get_yoy_comparison(db, "2+10")
    assert len(result) >= 1
    proj_a = [r for r in result if r["project_name"] == "Project A"][0]
    assert abs(proj_a["fy26"] - 15000000.0) < 1
    assert abs(proj_a["fy25"] - 12000000.0) < 1

def test_prior_snapshot_returns_none_when_missing(db):
    result = get_prior_snapshot_comparison(db, "2+10")
    assert result is None

def test_mtd_comparison(db):
    result = get_mtd_comparison(db, "2+10")
    assert len(result) == 2
    proj_a = [r for r in result if r["project_name"] == "Project A"][0]
    assert abs(proj_a["mtd_act"] - 1500000.0) < 1
    assert abs(proj_a["mtd_bud"] - 1300000.0) < 1


def test_sort_by_platform():
    data = [
        {"platform": "Promote", "project_name": "Z"},
        {"platform": "Core Fund", "project_name": "B"},
        {"platform": "Core Fund", "project_name": "A"},
        {"platform": "Dev JV2", "project_name": "C"},
    ]
    result = sort_by_platform(data)
    assert result[0]["platform"] == "Core Fund"
    assert result[0]["project_name"] == "A"
    assert result[1]["platform"] == "Core Fund"
    assert result[1]["project_name"] == "B"
    assert result[2]["platform"] == "Dev JV2"
    assert result[3]["platform"] == "Promote"


def test_platform_ordering_in_results(db):
    """Verify query results are sorted by platform order."""
    result = get_fee_by_platform_fy(db, "2+10")
    platforms = [r["platform"] for r in result]
    # Core Fund should come before Dev JV1
    assert platforms.index("Core Fund") < platforms.index("Dev JV1")


def test_prior_snapshot_comparison(db):
    prior_rows = [
        {"snapshot": "1+11", "platform": "Core Fund", "project_name": "Project A",
         "project_status": "Existing", "risk_category": "Committed",
         "fee_type": "Asset Mgmt Fee", "period_type": "forecast", "period": "FY26",
         "amount_usd": 13000000.0},
    ]
    db.insert_snapshot("1+11", prior_rows)
    result = get_prior_snapshot_comparison(db, "2+10")
    assert result is not None
    proj_a = [r for r in result if r["project_name"] == "Project A"][0]
    assert abs(proj_a["current_fcst"] - 15000000.0) < 1
    assert abs(proj_a["prior_fcst"] - 13000000.0) < 1
