---
name: fee-income-breakdown
description: |
  Fee income breakdown monthly updater for KSAMC/KSRM/KSLP entity data consolidation. Reads source Excel files from each entity (KSAMC Revenue breakdown, KSRM revenue tracking, KSLP Rev), populates the A5 Fee income breakdown master workbook's entity sheets, updates FY26 consolidation, refreshes Table sheet SUMIFS formulas, and verifies totals against the Summit BVI ERP consolidation file.

  Use this skill whenever the user mentions: fee income, fee income breakdown, A5 fee income, revenue breakdown, 수수료 수입, fee income back data, monthly fee update, or asks to update/populate fee income data from KSAMC/KSRM/KSLP source files. Also trigger when the user has files named like "A5_Fee income breakdown" or "Revenue breakdown" or "revenue tracking" and wants to consolidate monthly revenue data. Even casual requests like "fee income 업데이트해줘", "이번달 fee income 해줘", "수수료 데이터 붙여줘", "fee income 집계해줘" should trigger this skill.
---

# Fee Income Breakdown Monthly Updater

Updates the A5 Fee income breakdown master workbook each month by pulling actual revenue data from three entity source files (KSAMC, KSRM, KSLP), populating entity sheets, and ensuring the FY26 consolidation and Table dashboard stay in sync.

## Overview

The master workbook (`A5_Fee income breakdown back data_{Month} {YY}.xlsx`) is the central fee income tracking file. It contains:

- **Entity sheets** (KSAMC_{Month}, KSRM_{Month}, KSLP_{Month}): Raw monthly fee data by LP code/project
- **FY26 sheet**: Consolidation that aggregates entity data via SUMIFS, with both KRW (rows 90-164) and USD (rows 10-84, = KRW × FX rate)
- **Table sheet**: Dashboard with SUMIFS referencing FY26 for monthly fee income by Platform/Project/FeeType

The workflow runs monthly: new source files arrive → populate entity sheets → verify totals → everything flows through formulas to FY26 → Table.

## File Identification

### Master Workbook
- Pattern: `A5_Fee income breakdown back data_{Month} {YY}.xlsx`
- Examples: `A5_Fee income breakdown back data_Feb 26.xlsx`, `A5_Fee income breakdown back data_Mar 26.xlsx`

### Source Files (3 entities)
| Entity | Filename Pattern | Sheet to Read |
|--------|-----------------|---------------|
| KSAMC | `KSAMC Revenue breakdown_{date}(그룹보고).xlsx` | `미수수익_BPC reported(2025)` |
| KSRM | `KSRM_revenue traking_FY26 {Month}.xlsx` | `Revenue` |
| KSLP | `KSLP Rev_2026.xlsx` | `KSLP_2026` |

### Verification File
- Pattern: `2 Consolidation_Summit BVI_{Month}{YY}_v1.xlsx`
- Sheet: `Summit BVI_Con (ERP)`, Row 82 = Operations revenue

## Workflow

### Step 0: Period Transition (if updating to a new month)

When creating a new month's file from the previous month's:

1. **Copy and rename** the file: change `{OldMonth} {YY}` → `{NewMonth} {YY}`
2. **Rename entity sheets**: `KSAMC_{OldMonth}` → `KSAMC_{NewMonth}`, same for KSRM and KSLP
3. **Update all formula references** across all sheets: find-replace old sheet names in formulas (e.g., `KSAMC_Jan` → `KSAMC_Feb`)
4. **Update text labels** (headers, titles) that reference the old month
5. **Clear old actual data** from entity sheets if starting fresh for a new fiscal year

This step is complex because openpyxl doesn't automatically update formula references when sheets are renamed. You need to iterate through every cell in every sheet and string-replace old sheet names in formula strings.

### Step 1: Populate Entity Sheets from Source Files

For each entity, match rows between source and target by **LP code** (column H in target sheets).

Read `references/entity_structures.md` for the exact row-by-row structure of each entity sheet (KSAMC, KSRM, KSLP) including:
- Section boundaries (매입보수, 운용보수, 추가운용보수, PM Capex, Leasing, 성과보수)
- LP code positions and their corresponding source file rows
- Column mapping (which source column → which target column for each month)

#### Key Rules

1. **LP code matching**: Match source rows to target rows by LP code (e.g., LP00180, LP00310). Source files have LP codes in their own columns — check `references/entity_structures.md` for exact positions.

2. **Duplicate LP codes**: Some LP codes appear multiple times for different fund names (e.g., LP00180 maps to both AMB and DC이평 in KSAMC). When duplicates exist, match by both LP code AND fund name (column C or nearby identifier).

3. **Missing rows**: If a source file has an LP code with data but no matching row exists in the target, you may need to insert a new row in the appropriate section. After inserting:
   - Copy formatting from adjacent rows
   - Manually adjust SUM ranges that should include the new row (openpyxl `insert_rows` does NOT auto-expand formula ranges)
   - Check external sheet references (FY26, Total sheets) that point to rows below the insertion — they shift down by 1

4. **Data columns**: Monthly actuals go in columns I (Jan/month 1) through T (Dec/month 12). Column U often has a YTD total formula. Column 21 (U) sometimes has `=SUM(I:T)`.

5. **Only populate months that have data**: Don't overwrite future months that are still empty.

### Step 2: Verify Entity Totals

After populating, verify each entity's Grand Total matches the source file's total.

- KSAMC Grand Total: check the row marked "Grand Total" (row ~135, varies if rows were inserted)
- KSRM Grand Total: sum of all fee sections
- KSLP Grand Total: sum of all fee sections

Compare YTD totals (sum of all months populated so far) against source files.

### Step 3: Verify Against Summit BVI ERP Consolidation

Open the consolidation file and compare Operations revenue (Row 82) for each entity:

| Entity | Consolidation Column | Expected Match |
|--------|---------------------|----------------|
| KSAMC | Check column headers | KRW total should match exactly |
| KSRM | Check column headers | KRW total should match exactly |
| KSLP (ESR KS) | Check column headers | KRW total should match exactly |

**Known issue**: KSRM USD amount may differ by ~7,523 USD due to FX rate precision (source uses 0.000693, consolidation uses 0.00069). This is expected and documented. The KRW amounts should always match.

### Step 4: FY26 Sheet — Ensure Formulas Flow Correctly

The FY26 sheet has two sections:
- **Bottom (rows 90-164)**: KRW values via SUMIFS from entity sheets. These should auto-calculate once entity sheets are populated.
- **Top (rows 10-84)**: USD values = Bottom × FX rate (cell reference, typically 0.00069)

**Critical**: Row 8 may contain stale hardcoded values from a previous period. If the FY26 YTD total doesn't match the sum of entity totals, check Row 8 for leftover data and clear it to 0.

Row 4 formula: `=K8+K9` (feeds into overall totals). If Row 8 has stale data, the whole total chain is wrong.

### Step 5: Table Sheet — SUMIFS Linkage

The Table sheet (rows 3-275) aggregates FY26 data by Platform/Project/FeeType using SUMIFS formulas.

Read `references/table_formulas.md` for the exact SUMIFS formula pattern and the FY26 monthly block mapping that drives the formulas.

If the Table sheet already has correct SUMIFS formulas from a previous update, no action needed — the formulas auto-calculate when FY26 data changes.

If formulas need to be written (e.g., first time setup for a new FY, or Table headers were updated from FY25 to FY26):

1. Each Table row has: Platform (col B), Project (col C), FeeType (col F)
2. Columns J-U = monthly actuals (Jan-Dec)
3. Each cell = `SUMIFS(FY26!{fee_col}$90:{fee_col}$164, FY26!${plat_col}$90:${plat_col}$164, $B{row}, FY26!${proj_col}$90:${proj_col}$164, $C{row})`

The fee column depends on the FeeType and month — see `references/table_formulas.md` for the complete mapping.

4. Watch for duplicate (Platform, Project, FeeType) combinations in the Table. If duplicates exist, only one row should have formulas; clear the others to avoid double-counting.

### Step 6: Final Reconciliation

Verify: FY26 YTD Total = Sum of all entity YTD totals = Table YTD Total

If any mismatch:
- Check FY26 Row 8 for stale values
- Check for duplicate Table rows
- Check entity Grand Total formulas include all sections (especially after row insertions)

## Fee Type Categories

| Korean | English | Description |
|--------|---------|-------------|
| 매입보수 | Acquisition Fee | One-time fees on property acquisition |
| 운용보수 | Asset Management Fee | Recurring management fees by LP |
| 추가운용보수 | Additional AM Fee | Supplementary management fees |
| PM Capex | PM Capex Fee | Property management capital expenditure fees |
| Leasing Fee | Leasing Fee | Leasing-related fees |
| 성과보수 | Performance/Promote Fee | Performance-based incentive fees |

## Critical Pitfalls

1. **openpyxl insert_rows does NOT auto-expand formulas**: After inserting a row, you must manually fix every SUM/SUMIFS range that should include the new row, plus any external references from other sheets.

2. **Sheet rename requires manual formula updates**: openpyxl sheet renaming doesn't update formula strings. You must iterate all cells and string-replace old names.

3. **File permission errors**: The user may have the file open in Excel. Save to a temp path first, then copy with `shutil.copy2`, or save as a new version (v2, v3).

4. **LP code duplicates**: Always verify LP code + fund name, not just LP code alone.

5. **FY26 Row 8 stale data**: When transitioning from one fiscal year to another, Row 8 may retain old hardcoded USD values. Always check and clear.

6. **FX rate precision**: KSRM uses 0.000693 internally while Summit BVI consolidation uses 0.00069. This causes a small USD difference (~7,523 for Feb 26 data). KRW values always match.

### Step 7: Dashboard Update & Deploy

After the A5 workbook is finalized and the Revenue file's Summary_new template is updated:

1. **Parse Revenue file into dashboard**:
   ```python
   from src.parser import parse_excel_file
   from src.db import FeeIncomeDB
   db = FeeIncomeDB()
   db.init_db()
   rows, snapshot = parse_excel_file('<path_to_revenue_file>')
   db.insert_snapshot(snapshot, rows)
   db.save_snapshot_meta(snapshot, '<filename>')
   db.close()
   ```
   Working directory: `C:/Users/sjlee/OneDrive/GitHub/fee-income-dashboard/`

2. **Present summary to user for review**:
   - Show FY26 Fcst total and compare with previous snapshot if available
   - Show top 5 variance items (biggest |variance| vs budget)
   - Tell user: "Dashboard updated with {snapshot}. Please review at http://localhost:8501. Approve to push to cloud?"

3. **On user approval, push to cloud**:
   ```bash
   cd C:/Users/sjlee/OneDrive/GitHub/fee-income-dashboard
   git add -A
   git commit -m "data: update {snapshot} from {filename}"
   git push origin main
   ```
   This auto-deploys to Streamlit Cloud at the user's app URL.

4. **If user rejects**, ask what needs to be fixed and re-run relevant steps.

**Revenue file naming**: Must contain `Revenue_{YY}` and `({N}+{M})` in filename.
Examples: `Revenue_26 Fcst (3+9).xlsx`, `Revenue_26 Bud and 25 Fcst (3+9).xlsx`

## Reference Files

Read these before starting work:

- `references/entity_structures.md` — Detailed row-by-row structure of KSAMC, KSRM, KSLP entity sheets with LP codes, section boundaries, and source file column mappings
- `references/table_formulas.md` — FY26 monthly block mapping and SUMIFS formula patterns for the Table sheet
