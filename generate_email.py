"""Interactive email generation script.
Usage:
  py generate_email.py --snapshot 2+10 --dump-variances
  py generate_email.py --snapshot 2+10 --ytd-drivers '{"Proj": "driver"}' --fy-drivers '{"Proj": "driver"}'
"""
import argparse
import json
import sys
from src.db import FeeIncomeDB
from src.queries import get_ytd_comparison, get_fy_comparison, get_snapshot_n_value
from src.email_generator import build_email_data, render_email_html, MONTH_NAMES

def dump_variances(db, snapshot, top_n=5):
    n = get_snapshot_n_value(snapshot)
    month_name = MONTH_NAMES[n]
    ytd_data = get_ytd_comparison(db, snapshot)
    fy_data = get_fy_comparison(db, snapshot)
    ytd_built = build_email_data(ytd_data, {}, top_n=top_n)
    fy_built = build_email_data(fy_data, {}, top_n=top_n, act_col="fy_fcst", bud_col="fy_bud")
    output = {
        "snapshot": snapshot, "month_name": month_name,
        "ytd_key_items": [{"project_name": i["project_name"], "ytd_act_m": i["act_fmt"],
                           "ytd_bud_m": i["bud_fmt"], "variance_m": i["var_fmt"]}
                          for i in ytd_built["key_items"]],
        "fy_key_items": [{"project_name": i["project_name"], "fy_fcst_m": i["act_fmt"],
                          "fy_bud_m": i["bud_fmt"], "variance_m": i["var_fmt"]}
                         for i in fy_built["key_items"]],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

def generate_html(db, snapshot, ytd_drivers, fy_drivers, top_n=5):
    n = get_snapshot_n_value(snapshot)
    month_name = MONTH_NAMES[n]
    ytd_data = get_ytd_comparison(db, snapshot)
    fy_data = get_fy_comparison(db, snapshot)
    ytd_built = build_email_data(ytd_data, ytd_drivers, top_n=top_n)
    fy_built = build_email_data(fy_data, fy_drivers, top_n=top_n, act_col="fy_fcst", bud_col="fy_bud")
    html = render_email_html(snapshot, month_name, ytd_built, fy_built)
    print(html)

def main():
    parser = argparse.ArgumentParser(description="Fee Income Email Generator")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--dump-variances", action="store_true")
    parser.add_argument("--ytd-drivers", type=str, default="{}")
    parser.add_argument("--fy-drivers", type=str, default="{}")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--db-path", type=str, default="data/fee_income.db")
    args = parser.parse_args()
    db = FeeIncomeDB(args.db_path)
    db.init_db()
    if args.dump_variances:
        dump_variances(db, args.snapshot, args.top_n)
    else:
        ytd_drivers = json.loads(args.ytd_drivers)
        fy_drivers = json.loads(args.fy_drivers)
        generate_html(db, args.snapshot, ytd_drivers, fy_drivers, args.top_n)
    db.close()

if __name__ == "__main__":
    main()
