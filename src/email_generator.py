"""HTML email generation for fee income variance reports."""
from pathlib import Path
from jinja2 import Template

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "email.html"

def format_amount(value: float) -> str:
    return f"{value / 1_000_000:.1f}"

def format_variance(value: float) -> str:
    m = value / 1_000_000
    if m < -0.05:
        return f"({abs(m):.1f})"
    elif m > 0.05:
        return f"+{m:.1f}"
    return "0.0"

def build_email_data(comparison_data, drivers, top_n=5, act_col="ytd_act", bud_col="ytd_bud"):
    for row in comparison_data:
        row["_variance"] = row[act_col] - row[bud_col]
        row["_abs_var"] = abs(row["_variance"])
    sorted_data = sorted(comparison_data, key=lambda x: x["_abs_var"], reverse=True)
    key_items = sorted_data[:top_n]
    other_items = sorted_data[top_n:]

    grand_total_act = sum(r[act_col] for r in comparison_data)
    grand_total_bud = sum(r[bud_col] for r in comparison_data)
    grand_total_var = grand_total_act - grand_total_bud
    subtotal_act = sum(r[act_col] for r in key_items)
    subtotal_bud = sum(r[bud_col] for r in key_items)
    subtotal_var = subtotal_act - subtotal_bud
    other_act = sum(r[act_col] for r in other_items)
    other_bud = sum(r[bud_col] for r in other_items)
    other_var = other_act - other_bud

    formatted_items = []
    for item in key_items:
        name = item["project_name"]
        formatted_items.append({
            "project_name": name, "act": item[act_col], "bud": item[bud_col],
            "variance": item["_variance"], "driver": drivers.get(name, ""),
            "act_fmt": format_amount(item[act_col]), "bud_fmt": format_amount(item[bud_col]),
            "var_fmt": format_variance(item["_variance"]),
        })

    return {
        "key_items": formatted_items,
        "subtotal_act": subtotal_act, "subtotal_bud": subtotal_bud, "subtotal_var": subtotal_var,
        "subtotal_act_fmt": format_amount(subtotal_act), "subtotal_bud_fmt": format_amount(subtotal_bud),
        "subtotal_var_fmt": format_variance(subtotal_var),
        "other_act": other_act, "other_bud": other_bud, "other_var": other_var,
        "other_act_fmt": format_amount(other_act), "other_bud_fmt": format_amount(other_bud),
        "other_var_fmt": format_variance(other_var),
        "grand_total_act": grand_total_act, "grand_total_bud": grand_total_bud,
        "grand_total_var": grand_total_var,
        "grand_total_act_fmt": format_amount(grand_total_act),
        "grand_total_bud_fmt": format_amount(grand_total_bud),
        "grand_total_var_fmt": format_variance(grand_total_var),
    }

def render_email_html(snapshot, month_name, ytd_data, fy_data, greeting=None):
    if greeting is None:
        greeting = (f"{snapshot} Revenue 파일 공유드립니다.<br/>"
                    f"다음주 월요일 리뷰 후 PL에 반영하도록 하겠습니다. 감사합니다.")
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_text)
    return template.render(greeting=greeting, month_name=month_name, ytd=ytd_data, fy=fy_data)
