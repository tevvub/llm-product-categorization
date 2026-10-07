"""
Build an Excel labeling workbook from a product_sample_round{N}.csv:

  - ProductSeries column is blanked out and gets an Excel dropdown (data
    validation list) of the 24 valid category values, so a human/LLM-assisted
    labeler picks from a fixed list instead of typing free text.
  - The true (original) ProductSeries values are NOT included in the
    workbook -- they're written to a separate answer-key CSV for later
    scoring, so the labeling file stays "blind."

Usage:
    py scripts/make_labeling_workbook.py
"""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# ---- Config -----------------------------------------------------------
ROUND = 2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
SAMPLE_CSV = OUTPUT_DIR / f"product_sample_round{ROUND}.csv"
WORKBOOK_XLSX = OUTPUT_DIR / f"product_sample_round{ROUND}.xlsx"
ANSWER_KEY_CSV = OUTPUT_DIR / f"product_sample_round{ROUND}_answer_key.csv"

ID_COLUMN = "ProductId"
CATEGORY_COLUMN = "ProductSeries"

LABELING_SHEET_NAME = "Labeling"
CATEGORY_LIST_SHEET_NAME = "Category List"

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def main() -> None:
    sample = pd.read_csv(SAMPLE_CSV, dtype={ID_COLUMN: "Int64"})

    # Answer key: true category values, kept out of the labeling workbook.
    sample[[ID_COLUMN, CATEGORY_COLUMN]].to_csv(ANSWER_KEY_CSV, index=False)

    categories = sorted(sample[CATEGORY_COLUMN].dropna().unique().tolist())

    labeling = sample.drop(columns=[CATEGORY_COLUMN]).copy()
    labeling[CATEGORY_COLUMN] = ""

    wb = Workbook()

    # ---- Labeling sheet ----
    ws = wb.active
    ws.title = LABELING_SHEET_NAME

    headers = list(labeling.columns)
    ws.append(headers)
    for col_idx, _ in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="left")

    for row in labeling.itertuples(index=False):
        ws.append(list(row))

    ws.freeze_panes = "A2"

    widths = {"Round": 8, "ProductId": 12, "VendorName": 28, "Product": 40, "ProductSeries": 32}
    for col_idx, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = widths.get(header, 20)

    # ---- Category List sheet (dropdown source) ----
    cat_ws = wb.create_sheet(CATEGORY_LIST_SHEET_NAME)
    cat_ws.append([CATEGORY_COLUMN])
    cat_ws.cell(row=1, column=1).font = Font(bold=True)
    for i, cat in enumerate(categories, start=2):
        cat_ws.cell(row=i, column=1, value=cat)
    cat_ws.column_dimensions["A"].width = 32
    cat_ws.sheet_state = "hidden"

    last_cat_row = len(categories) + 1
    dv_formula = f"='{CATEGORY_LIST_SHEET_NAME}'!$A$2:$A${last_cat_row}"
    dv = DataValidation(
        type="list",
        formula1=dv_formula,
        allow_blank=True,
        showDropDown=False,  # openpyxl quirk: False is what actually shows the in-cell arrow
        showErrorMessage=True,
        errorTitle="Invalid ProductSeries",
        error="Please choose a value from the dropdown list.",
    )
    category_col_idx = headers.index(CATEGORY_COLUMN) + 1
    category_col_letter = get_column_letter(category_col_idx)
    dv.add(f"{category_col_letter}2:{category_col_letter}{len(labeling) + 1}")
    ws.add_data_validation(dv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(WORKBOOK_XLSX)

    print(f"Labeling workbook: {WORKBOOK_XLSX}")
    print(f"  {len(labeling)} rows, dropdown column '{CATEGORY_COLUMN}' ({len(categories)} options), starts blank")
    print(f"Answer key:        {ANSWER_KEY_CSV}")


if __name__ == "__main__":
    main()
