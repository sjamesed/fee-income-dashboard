# Entity Sheet Structures

Detailed row-by-row structure of each entity sheet in the A5 Fee income breakdown master workbook.

## Common Column Layout

All entity sheets share this column structure:
- **Col A**: Section headers (매입보수, 운용보수, etc.)
- **Col B**: Sub-section labels, totals
- **Col C**: Fund/Project Korean name
- **Col D**: Fund/Project English name
- **Col E**: Fund type
- **Col F**: Company code
- **Col G**: Fee type code
- **Col H**: LP code (primary matching key)
- **Col I**: January actual
- **Col J**: February actual
- **Col K-T**: March through December actuals
- **Col U (21)**: YTD Total formula (typically `=SUM(I:T)`)

Monthly data columns: I=Jan(9), J=Feb(10), K=Mar(11), L=Apr(12), M=May(13), N=Jun(14), O=Jul(15), P=Aug(16), Q=Sep(17), R=Oct(18), S=Nov(19), T=Dec(20)

## KSAMC_{Month} Sheet

### Section Layout (as of Feb 26, after row insertions)

| Section | Rows | Description |
|---------|------|-------------|
| Header | 1-5 | Column headers, entity name, period |
| 매입보수 (Acquisition) | 6-8 | 2-3 REIT acquisition fees |
| (blank/separator) | 9-16 | Spacing rows |
| 운용보수 (AM Fee) | 17-61 | ~45 LP entries for asset management |
| 운용보수 Total | 62 | `=SUM(I17:I61)` |
| (blank) | 63-68 | Spacing |
| 추가운용보수 (Add'l AM) | 69-76 | ~8 additional AM fee entries |
| 추가운용보수 Total | 77 | `=SUM(I69:I76)` |
| (blank) | 78-84 | Spacing |
| PM Capex | 85-89 | ~5 PM Capex entries |
| PM Capex Total | 90 | `=SUM(I85:I89)` |
| (blank) | 91-95 | Spacing |
| Leasing Fee | 96-114 | ~19 Leasing entries (may grow with insertions) |
| Leasing Total | 115 | `=SUM(I96:I114)` |
| (blank) | 116-122 | Spacing |
| 성과보수 (Performance) | 123-130 | ~8 performance fee entries |
| 성과보수 Total | 131 | `=SUM(I123:I130)` |
| (blank) | 132-134 | Spacing |
| Grand Total | 135 | `=I8+I10+I62+I77+I90+I115+I131` |

**Note**: Row numbers shift when rows are inserted (e.g., adding a new Leasing LP). After any insertion, verify and fix all SUM ranges and the Grand Total formula.

### Known Duplicate LP Codes
- **LP00180**: Appears twice — once for AMB (row ~28) and once for DC이평 (row ~29). Match by fund name (col C), not just LP code.

### Source File: KSAMC Revenue breakdown
- Sheet: `미수수익_BPC reported(2025)`
- LP code column: varies by section (check column B or C)
- Monthly columns: typically col 4+ for Jan, col 5+ for Feb, etc.
- Match target rows by LP code
- For LP00180 duplicates, match by fund name additionally

## KSRM_{Month} Sheet

### Section Layout

| Section | Rows | Description |
|---------|------|-------------|
| Header | 1-4 | Column headers |
| FY26 data | 5-14 | Current FY entries (자리츠1, 자리츠2, 모리츠, etc.) |
| FY26 Total | ~14 | Subtotal for current FY |
| (blank) | 15-18 | Spacing |
| FY24 data | 19-29 | Previous year carryover entries |
| FY24 Total | ~29 | Subtotal |
| FY23 data | 35-45 | Two years ago |
| FY22/FY21 | 50-74 | Historical |
| Grand Total | ~77-80 | Combines all FY sections |

### Source File: KSRM_revenue traking
- Sheet: `Revenue`
- Organized by fiscal year sections
- Match by asset name (자리츠1, 자리츠2, etc.) and fund category
- Monthly columns start at column 5 or 6 (verify header row)

## KSLP_{Month} Sheet

### Section Layout

| Section | Rows | Description |
|---------|------|-------------|
| Header | 1-4 | Column headers |
| ESRKS main | 5-6 | Bupyeong Data Center |
| Asset list | 9-29 | 20 entities (김포, 김해, 부천콜드, 마장, etc.) |
| Asset Total | 29 | Subtotal |
| Bupyeong IDC | 32-34 | IDC group |
| REIT entities | 37-44 | Sub1, Sub2, Sub3, Parent, PFVs |
| REIT Total | 44 | Subtotal |
| 내부거래 (Internal) | 50-55 | Internal transactions (KSRM, KSAMC, etc.) |
| Internal Total | 55 | Subtotal |
| (spacing) | 56-70 | |
| Logos group | 71-76 | Logos assets |
| Logos Total | 76 | Subtotal |
| Grand Total | 83 | `=H6+H29+H34+H44+H62+H76+H55` (approx) |

### Source File: KSLP Rev_2026
- Sheet: `KSLP_2026`
- Two-tier: AM Fee and PM Fee sections
- Entities listed by project name
- Monthly columns starting at col 4-5

## Data Population Process

For each entity:

1. Open source file with `openpyxl.load_workbook(path, data_only=True)` to get computed values
2. Open target file with `openpyxl.load_workbook(path, data_only=False)` to preserve formulas
3. For each row in source with data:
   a. Find matching LP code in target sheet column H
   b. If duplicate LP code, also match fund name
   c. Write monthly values to the correct column (I=Jan, J=Feb, etc.)
4. If source has an LP code not found in target:
   a. Determine which section it belongs to
   b. Insert a new row in that section using `ws.insert_rows(row_num)`
   c. Copy formatting from adjacent row
   d. Fix all affected SUM ranges and external references
5. Save workbook

### Post-Population Checks
- Entity Grand Total should match source file total
- Check for any zero/blank cells where data was expected
- Verify no formula cells were accidentally overwritten with values
