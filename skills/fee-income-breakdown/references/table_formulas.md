# Table Sheet SUMIFS Formulas

The Table sheet aggregates FY26 data into a flat dashboard format using SUMIFS formulas.

## Table Sheet Structure

- **Row 1**: SUBTOTAL formulas for column totals
- **Row 2**: Headers
- **Rows 3-275**: Data rows (Platform × Project × FeeType combinations)

### Table Columns

| Col | Letter | Content |
|-----|--------|---------|
| 2 | B | Platform |
| 3 | C | Project Name |
| 4 | D | Status |
| 5 | E | Risk Category |
| 6 | F | Fee Type |
| 7 | G | FY26 YTD Actual (`=SUM(J:U)` for that row) |
| 8 | H | FY26 Budget (10+2) |
| 9 | I | FY24 Actual |
| 10 | J | January |
| 11 | K | February |
| 12 | L | March |
| 13 | M | April |
| 14 | N | May |
| 15 | O | June |
| 16 | P | July |
| 17 | Q | August |
| 18 | R | September |
| 19 | S | October |
| 20 | T | November |
| 21 | U | December |

## FY26 Monthly Block Mapping

The FY26 sheet (bottom section, rows 90-164) organizes data in 12 monthly blocks. Each block has columns for Platform, Project, and 6 fee types.

| Month | Table Col | FY26 Platform Col | FY26 Project Col | Fee Type Start Col |
|-------|-----------|-------------------|------------------|--------------------|
| Jan | J (10) | M (13) | N (14) | P (16) |
| Feb | K (11) | X (24) | Y (25) | AA (27) |
| Mar | L (12) | AI (35) | AJ (36) | AL (38) |
| Apr | M (13) | AT (46) | AU (47) | AW (49) |
| May | N (14) | BE (57) | BF (58) | BH (60) |
| Jun | O (15) | BP (68) | BQ (69) | BS (71) |
| Jul | P (16) | CA (79) | CB (80) | CD (82) |
| Aug | Q (17) | CL (90) | CM (91) | CO (93) |
| Sep | R (18) | CW (101) | CX (102) | CZ (104) |
| Oct | S (19) | DH (112) | DI (113) | DK (115) |
| Nov | T (20) | DS (123) | DT (124) | DV (126) |
| Dec | U (21) | ED (134) | EE (135) | EG (137) |

### Fee Type Offsets Within Each Monthly Block

From the "Fee Type Start Col" for each month, the 6 fee types are at these offsets:

| Offset | Fee Type | Table FeeType Value |
|--------|----------|-------------------|
| +0 | Asset Management (운용보수) | Asset Mgmt |
| +1 | Development Management (매입보수) | Dev Mgmt |
| +2 | Leasing (Leasing Fee) | Leasing |
| +3 | Acquisition/Divestiture (추가운용보수) | Acq/Div |
| +4 | Promote (성과보수) | Promote |
| +5 | Other (PM Capex etc.) | Other |

### Fee Type Mapping

Map Table column F values to FY26 fee column offsets:

| Table FeeType (col F) | Offset from Fee Start |
|----------------------|----------------------|
| Asset Mgmt | 0 |
| Dev Mgmt | 1 |
| Leasing | 2 |
| Acq/Div | 3 |
| Promote | 4 |
| Other | 5 |

## SUMIFS Formula Pattern

For each cell in Table rows 3-275, columns J-U:

```
=SUMIFS(
  FY26!{fee_col}$90:{fee_col}$164,
  FY26!${plat_col}$90:${plat_col}$164, $B{row},
  FY26!${proj_col}$90:${proj_col}$164, $C{row}
)
```

Where:
- `{fee_col}` = Fee Type Start Col + fee type offset (from tables above)
- `{plat_col}` = Platform column for that month
- `{proj_col}` = Project column for that month
- `{row}` = current Table row number

### Example

For Table row 5, column K (February), FeeType = "Asset Mgmt":
- Feb Platform col = X (24)
- Feb Project col = Y (25)
- Feb Fee Start = AA (27), Asset Mgmt offset = 0, so fee col = AA (27)

Formula: `=SUMIFS(FY26!AA$90:AA$164, FY26!$X$90:$X$164, $B5, FY26!$Y$90:$Y$164, $C5)`

### Python Code Pattern for Formula Generation

```python
from openpyxl.utils import get_column_letter

# Monthly block definitions
months = [
    {"table_col": 10, "plat_col": 13, "proj_col": 14, "fee_start": 16},  # Jan
    {"table_col": 11, "plat_col": 24, "proj_col": 25, "fee_start": 27},  # Feb
    {"table_col": 12, "plat_col": 35, "proj_col": 36, "fee_start": 38},  # Mar
    {"table_col": 13, "plat_col": 46, "proj_col": 47, "fee_start": 49},  # Apr
    {"table_col": 14, "plat_col": 57, "proj_col": 58, "fee_start": 60},  # May
    {"table_col": 15, "plat_col": 68, "proj_col": 69, "fee_start": 71},  # Jun
    {"table_col": 16, "plat_col": 79, "proj_col": 80, "fee_start": 82},  # Jul
    {"table_col": 17, "plat_col": 90, "proj_col": 91, "fee_start": 93},  # Aug
    {"table_col": 18, "plat_col": 101, "proj_col": 102, "fee_start": 104},  # Sep
    {"table_col": 19, "plat_col": 112, "proj_col": 113, "fee_start": 115},  # Oct
    {"table_col": 20, "plat_col": 123, "proj_col": 124, "fee_start": 126},  # Nov
    {"table_col": 21, "plat_col": 134, "proj_col": 135, "fee_start": 137},  # Dec
]

fee_type_map = {
    "Asset Mgmt": 0,
    "Dev Mgmt": 1,
    "Leasing": 2,
    "Acq/Div": 3,
    "Promote": 4,
    "Other": 5,
}

def write_sumifs(ws_table, ws_fy26_name="FY26"):
    for row in range(3, 276):  # Table data rows
        fee_type = ws_table.cell(row=row, column=6).value  # Col F
        if not fee_type or fee_type not in fee_type_map:
            continue
        offset = fee_type_map[fee_type]

        for m in months:
            fee_col = get_column_letter(m["fee_start"] + offset)
            plat_col = get_column_letter(m["plat_col"])
            proj_col = get_column_letter(m["proj_col"])

            formula = (
                f"=SUMIFS({ws_fy26_name}!{fee_col}$90:{fee_col}$164,"
                f"{ws_fy26_name}!${plat_col}$90:${plat_col}$164,$B{row},"
                f"{ws_fy26_name}!${proj_col}$90:${proj_col}$164,$C{row})"
            )
            ws_table.cell(row=row, column=m["table_col"]).value = formula
```

## Handling Duplicates

Some (Platform, Project, FeeType) combinations may appear in multiple Table rows. This causes double-counting since the same SUMIFS formula would return the same value in each duplicate row.

To handle:
1. Identify duplicates: group by (col B, col C, col F) and find rows with count > 1
2. Keep formulas in the first occurrence only
3. Clear formulas in subsequent occurrences (set to 0 or blank)

Known duplicates as of Feb 26:
- Anpyeong Drop: 5 duplicate rows (rows 148-152 area)
- West Icheon: 1 duplicate row (row ~210)
