import pytest
from src.email_generator import format_amount, format_variance, build_email_data, render_email_html

def test_format_amount_positive():
    assert format_amount(1500000) == "1.5"

def test_format_amount_zero():
    assert format_amount(0) == "0.0"

def test_format_variance_positive():
    assert format_variance(1500000) == "+1.5"

def test_format_variance_negative():
    assert format_variance(-800000) == "(0.8)"

def test_format_variance_zero():
    assert format_variance(0) == "0.0"

def test_build_email_data():
    ytd_data = [
        {"project_name": "Proj A", "platform": "P1", "ytd_act": 5000000, "ytd_bud": 3000000},
        {"project_name": "Proj B", "platform": "P1", "ytd_act": 1000000, "ytd_bud": 1500000},
        {"project_name": "Proj C", "platform": "P2", "ytd_act": 100000, "ytd_bud": 110000},
    ]
    drivers = {"Proj A": "Leasing fee increase", "Proj B": "Delay in closing"}
    result = build_email_data(ytd_data, drivers, top_n=2)
    assert len(result["key_items"]) == 2
    assert result["key_items"][0]["project_name"] == "Proj A"
    assert result["other_act"] == 100000
    assert result["other_bud"] == 110000
    assert result["grand_total_act"] == 6100000
    assert result["grand_total_bud"] == 4610000

def test_render_email_html():
    ytd_items = {
        "key_items": [{"project_name": "Proj A", "act": 5000000, "bud": 3000000,
                        "variance": 2000000, "driver": "Test driver",
                        "act_fmt": "5.0", "bud_fmt": "3.0", "var_fmt": "+2.0"}],
        "subtotal_act": 5000000, "subtotal_bud": 3000000, "subtotal_var": 2000000,
        "subtotal_act_fmt": "5.0", "subtotal_bud_fmt": "3.0", "subtotal_var_fmt": "+2.0",
        "other_act": 100000, "other_bud": 110000, "other_var": -10000,
        "other_act_fmt": "0.1", "other_bud_fmt": "0.1", "other_var_fmt": "0.0",
        "grand_total_act": 5100000, "grand_total_bud": 3110000, "grand_total_var": 1990000,
        "grand_total_act_fmt": "5.1", "grand_total_bud_fmt": "3.1", "grand_total_var_fmt": "+2.0",
    }
    fy_items = {
        "key_items": [], "subtotal_act": 0, "subtotal_bud": 0, "subtotal_var": 0,
        "subtotal_act_fmt": "0.0", "subtotal_bud_fmt": "0.0", "subtotal_var_fmt": "0.0",
        "other_act": 0, "other_bud": 0, "other_var": 0,
        "other_act_fmt": "0.0", "other_bud_fmt": "0.0", "other_var_fmt": "0.0",
        "grand_total_act": 0, "grand_total_bud": 0, "grand_total_var": 0,
        "grand_total_act_fmt": "0.0", "grand_total_bud_fmt": "0.0", "grand_total_var_fmt": "0.0",
    }
    html = render_email_html(snapshot="2+10", month_name="Feb", ytd_data=ytd_items, fy_data=fy_items)
    assert "Proj A" in html
    assert "Test driver" in html
    assert "YTD Feb Act" in html
    assert "Seungjoon Lee" in html
