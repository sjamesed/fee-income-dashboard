"""Common SQL queries for fee income analysis."""

PLATFORM_ORDER = [
    "Core Fund",
    "Dev JV1 - Byul",
    "Dev JV2",
    "Income JV",
    "Others/Outbound",
    "Credit Fund",
    "Samsung Discretionary Fund",
    "Data Center",
    "REIT (JV)",
    "REIT (3rd party)",
    "FX impact",
    "Promote",
]


def sort_by_platform(data: list[dict], platform_key: str = "platform") -> list[dict]:
    """Sort a list of dicts by PLATFORM_ORDER, then by project_name if present."""
    order_map = {name: i for i, name in enumerate(PLATFORM_ORDER)}
    default = len(PLATFORM_ORDER)

    def sort_key(row):
        plat_idx = order_map.get(row.get(platform_key, ""), default)
        proj = row.get("project_name", "")
        return (plat_idx, proj)

    return sorted(data, key=sort_key)


def get_snapshot_n_value(snapshot: str) -> int:
    """Extract N from snapshot like 'FY26 2+10' or '2+10'."""
    import re
    match = re.search(r"(\d+)\+\d+", snapshot)
    return int(match.group(1)) if match else 0


def get_fee_by_project_fy(db, snapshot: str) -> list[dict]:
    rows = db.query("""
        SELECT project_name, platform,
            SUM(CASE WHEN period = 'FY23' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy23_act,
            SUM(CASE WHEN period = 'FY24' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy24_act,
            SUM(CASE WHEN period = 'FY25' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy25_act,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'budget' THEN amount_usd ELSE 0 END) as fy26_bud,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'forecast' THEN amount_usd ELSE 0 END) as fy26_fcst
        FROM fee_income WHERE snapshot = ? AND period IN ('FY23', 'FY24', 'FY25', 'FY26')
        GROUP BY project_name, platform
        HAVING (fy23_act + fy24_act + fy25_act + fy26_bud + fy26_fcst) != 0
    """, (snapshot,))
    return sort_by_platform(rows)


def get_fee_by_platform_fy(db, snapshot: str) -> list[dict]:
    rows = db.query("""
        SELECT platform,
            SUM(CASE WHEN period = 'FY23' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy23_act,
            SUM(CASE WHEN period = 'FY24' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy24_act,
            SUM(CASE WHEN period = 'FY25' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy25_act,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'budget' THEN amount_usd ELSE 0 END) as fy26_bud,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'forecast' THEN amount_usd ELSE 0 END) as fy26_fcst
        FROM fee_income WHERE snapshot = ? AND period IN ('FY23', 'FY24', 'FY25', 'FY26')
        GROUP BY platform
        HAVING (fy23_act + fy24_act + fy25_act + fy26_bud + fy26_fcst) != 0
    """, (snapshot,))
    return sort_by_platform(rows)


def _build_month_list(year: int, n_months: int) -> list[str]:
    return [f"{year}-{m:02d}" for m in range(1, n_months + 1)]


def get_mtd_comparison(db, snapshot: str) -> list[dict]:
    n = get_snapshot_n_value(snapshot)
    month = f"2026-{n:02d}"
    rows = db.query("""
        SELECT project_name, platform,
            SUM(CASE WHEN period_type = 'actual' THEN amount_usd ELSE 0 END) as mtd_act,
            SUM(CASE WHEN period_type = 'budget' THEN amount_usd ELSE 0 END) as mtd_bud
        FROM fee_income
        WHERE snapshot = ? AND period = ? AND period_type IN ('actual', 'budget')
        GROUP BY project_name, platform
        HAVING (mtd_act + mtd_bud) != 0
        ORDER BY ABS(mtd_act - mtd_bud) DESC
    """, (snapshot, month))
    return sort_by_platform(rows)


def get_ytd_comparison(db, snapshot: str) -> list[dict]:
    n = get_snapshot_n_value(snapshot)
    months = _build_month_list(2026, n)
    placeholders = ",".join(["?"] * len(months))
    rows = db.query(f"""
        SELECT project_name, platform,
            SUM(CASE WHEN period_type = 'actual' THEN amount_usd ELSE 0 END) as ytd_act,
            SUM(CASE WHEN period_type = 'budget' THEN amount_usd ELSE 0 END) as ytd_bud
        FROM fee_income
        WHERE snapshot = ? AND period IN ({placeholders}) AND period_type IN ('actual', 'budget')
        GROUP BY project_name, platform
        HAVING (ytd_act + ytd_bud) != 0
    """, (snapshot, *months))
    return sort_by_platform(rows)


def get_fy_comparison(db, snapshot: str) -> list[dict]:
    rows = db.query("""
        SELECT project_name, platform,
            SUM(CASE WHEN period_type = 'forecast' THEN amount_usd ELSE 0 END) as fy_fcst,
            SUM(CASE WHEN period_type = 'budget' THEN amount_usd ELSE 0 END) as fy_bud
        FROM fee_income
        WHERE snapshot = ? AND period = 'FY26' AND period_type IN ('forecast', 'budget')
        GROUP BY project_name, platform
        HAVING (fy_fcst + fy_bud) != 0
    """, (snapshot,))
    return sort_by_platform(rows)


def get_prior_snapshot_comparison(db, current_snapshot: str) -> list[dict] | None:
    current_n = get_snapshot_n_value(current_snapshot)
    prior_n = current_n - 1
    if prior_n < 1:
        return None
    snapshots = db.list_snapshots()
    prior = None
    for s in snapshots:
        if get_snapshot_n_value(s) == prior_n:
            prior = s
            break
    if prior is None:
        return None
    rows = db.query("""
        SELECT project_name, platform, current_fcst, prior_fcst FROM (
            SELECT
                COALESCE(c.project_name, p.project_name) as project_name,
                COALESCE(c.platform, p.platform) as platform,
                COALESCE(c.fy_fcst, 0) as current_fcst,
                COALESCE(p.fy_fcst, 0) as prior_fcst
            FROM (
                SELECT project_name, platform, SUM(amount_usd) as fy_fcst
                FROM fee_income WHERE snapshot = ? AND period = 'FY26' AND period_type = 'forecast'
                GROUP BY project_name, platform
            ) c
            LEFT JOIN (
                SELECT project_name, platform, SUM(amount_usd) as fy_fcst
                FROM fee_income WHERE snapshot = ? AND period = 'FY26' AND period_type = 'forecast'
                GROUP BY project_name, platform
            ) p ON c.project_name = p.project_name AND c.platform = p.platform

            UNION

            SELECT p2.project_name, p2.platform, 0 as current_fcst, p2.fy_fcst as prior_fcst
            FROM (
                SELECT project_name, platform, SUM(amount_usd) as fy_fcst
                FROM fee_income WHERE snapshot = ? AND period = 'FY26' AND period_type = 'forecast'
                GROUP BY project_name, platform
            ) p2
            LEFT JOIN (
                SELECT project_name, platform
                FROM fee_income WHERE snapshot = ? AND period = 'FY26' AND period_type = 'forecast'
                GROUP BY project_name, platform
            ) c2 ON p2.project_name = c2.project_name AND p2.platform = c2.platform
            WHERE c2.project_name IS NULL
        )
    """, (current_snapshot, prior, prior, current_snapshot))
    return sort_by_platform(rows)


def get_yoy_comparison(db, snapshot: str) -> list[dict]:
    rows = db.query("""
        SELECT project_name, platform,
            SUM(CASE WHEN period = 'FY26' AND period_type = 'forecast' THEN amount_usd ELSE 0 END) as fy26,
            SUM(CASE WHEN period = 'FY25' AND period_type = 'actual' THEN amount_usd ELSE 0 END) as fy25
        FROM fee_income
        WHERE snapshot = ? AND period IN ('FY25', 'FY26') AND period_type IN ('actual', 'forecast')
        GROUP BY project_name, platform
        HAVING (fy26 + fy25) != 0
    """, (snapshot,))
    return sort_by_platform(rows)
