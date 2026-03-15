import pytest
from src.parser import (
    extract_snapshot_from_filename,
    parse_annual_header,
    parse_monthly_header,
    parse_excel_file,
)


def test_extract_snapshot_basic():
    assert extract_snapshot_from_filename("Revenue_26 Bud and 25 Fcst (2+10).xlsx") == "FY26 2+10"

def test_extract_snapshot_short_name():
    assert extract_snapshot_from_filename("Revenue_26 Fcst (3+9).xlsx") == "FY26 3+9"

def test_extract_snapshot_year_end():
    assert extract_snapshot_from_filename("Revenue_26 Bud and 25 Fcst (12+0).xlsx") == "FY26 12+0"

def test_extract_snapshot_fy27():
    assert extract_snapshot_from_filename("Revenue_27 Fcst (1+11).xlsx") == "FY27 1+11"

def test_extract_snapshot_invalid():
    with pytest.raises(ValueError):
        extract_snapshot_from_filename("random_file.xlsx")

def test_parse_annual_header_fy_act():
    period, period_type = parse_annual_header("FY23 (act)")
    assert period == "FY23"
    assert period_type == "actual"

def test_parse_annual_header_fy_bud():
    period, period_type = parse_annual_header("FY25 (Bud)")
    assert period == "FY25"
    assert period_type == "budget"

def test_parse_annual_header_fy_act_no_parens():
    period, period_type = parse_annual_header("FY25 Act")
    assert period == "FY25"
    assert period_type == "actual"

def test_parse_annual_header_fy_5yr():
    period, period_type = parse_annual_header("FY25 (5yr refcst)")
    assert period == "FY25"
    assert period_type == "reforecast"

def test_parse_annual_header_half_year():
    period, period_type = parse_annual_header("1H25 Act")
    assert period == "1H25"
    assert period_type == "actual"

def test_parse_annual_header_half_year_bud():
    period, period_type = parse_annual_header("2H26 (Bud)")
    assert period == "2H26"
    assert period_type == "budget"

def test_parse_annual_header_fy26_fcst():
    period, period_type = parse_annual_header("FY26 Fcst")
    assert period == "FY26"
    assert period_type == "forecast"

def test_parse_monthly_header_act():
    period, period_type = parse_monthly_header("Jan-25 (Act)")
    assert period == "2025-01"
    assert period_type == "actual"

def test_parse_monthly_header_bud():
    period, period_type = parse_monthly_header("Jan 24 (Bud)")
    assert period == "2024-01"
    assert period_type == "budget"

def test_parse_monthly_header_forecast():
    period, period_type = parse_monthly_header("Mar-26 (2+10)")
    assert period == "2026-03"
    assert period_type == "forecast"

def test_parse_monthly_header_plain():
    period, period_type = parse_monthly_header("Jan-23")
    assert period == "2023-01"
    assert period_type == "actual"

def test_parse_excel_file_real():
    import os
    import re
    filepath = "C:/Users/sjlee/AppData/Local/Temp/revenue.xlsx"
    if not os.path.exists(filepath):
        pytest.skip("Test Excel file not available")
    if not re.search(r"\(\d+\+\d+\)", os.path.basename(filepath)):
        pytest.skip("Test Excel file does not contain snapshot pattern in filename")
    rows, snapshot = parse_excel_file(filepath)
    assert snapshot == "12+0"
    assert len(rows) > 0
    required_keys = {"snapshot", "platform", "project_name", "fee_type", "period_type", "period", "amount_usd"}
    assert required_keys.issubset(rows[0].keys())
    bucheon_am = [r for r in rows if r["project_name"] == "Bucheon LP"
                  and r["fee_type"] == "Asset Mgmt Fee"
                  and r["period"] == "FY25"
                  and r["period_type"] == "actual"]
    assert len(bucheon_am) == 1
    assert abs(bucheon_am[0]["amount_usd"] - 4026715.89) < 1
