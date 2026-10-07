# LLM Product Categorization — Sample Set

A reproducible random sample of products drawn from `Master_Data_2022_final.csv`,
intended as a labeling set for evaluating LLM-based product security categorization.
Each sampling pass is tagged with a `Round` number; rounds are drawn to never
overlap, so they can be pooled into one growing labeled set over time.

## Source data

- **File:** `NSF Proposal/data/output/Master_Data_2022_final.csv`
  (full path: `C:\Users\mutal\OneDrive - University of Tulsa\NSF Proposal\data\output\Master_Data_2022_final.csv`)
- **Rows:** 10,380 products
- **Columns:** 63 total in source; **5 retained** in each round's output:
  `Round, ProductId, VendorName, Product, ProductSeries`

## Round 1 — 150 products, full category coverage

An earlier plain-random draw of 100 products (`data/archive/product_sample_100_draft_v1.csv`)
missed 3 of the 24 `ProductSeries` categories (**Hardware, Operations, Other**). Round 1
fixes that by guaranteeing every category appears at least once.

### Method

1. Shuffle the full 10,380-product list once with a fixed random seed.
2. Walk the shuffled order and take the first product seen for each of the 24
   `ProductSeries` values — guarantees full category coverage while still being
   a random pick within each category.
3. Continue down the same shuffled order, taking the next unused rows, until
   the sample reaches 150 products (24 coverage picks + 126 additional random picks).
4. Sort the final sample by `ProductId` and tag every row with `Round = 1`.

- Random seed: **42**
- Category column used for coverage: `ProductSeries` (24 unique values, no nulls).
  Note: `ProductCategory` has 178 unique values — too many to guarantee coverage
  in a 150-row sample, so it was not used as the coverage target.
- Products: see `sampled_product_ids` in `data/output/product_sample_round1_manifest.json` (150 IDs)
- **Note:** `product_sample_round1.csv` (the plain CSV with true labels filled in) is no
  longer present in `data/output/` — only the labeling `.xlsx`, the answer key, and the
  manifest remain. The manifest's `sampled_product_ids` is the authoritative record of
  which 150 products are in Round 1 (and is what Round 2's exclusion logic reads).

## Round 2 — 100 products, full category coverage, excludes Round 1

Same method as Round 1, with one addition: every `ProductId` already used in Round 1
is removed from the sampling pool *before* shuffling, so Round 2 is guaranteed to be
disjoint from Round 1.

### Method

1. Load all prior rounds' `sampled_product_ids` from `data/output/product_sample_round*_manifest.json`
   (auto-detected — Round 1's 150 IDs) and drop them from the candidate pool
   (10,380 → 10,230 eligible products).
2. Shuffle the remaining pool once with a fixed random seed.
3. Take the first product seen per `ProductSeries` (24 categories) for coverage,
   then fill the remaining slots from the same shuffled order, until 100 products
   are reached (24 coverage picks + 76 additional random picks).
4. Sort by `ProductId`, tag every row `Round = 2`, and assert zero overlap with Round 1
   before writing output (script raises an error otherwise).

- Random seed: **7** (different from Round 1's 42, since Round 1's seed applied to the
  full 10,380-product pool — reusing it here would just reproduce a shuffle order that's
  no longer meaningful once 150 products are removed; a fresh seed keeps the two rounds'
  draws independent rather than correlated sub-sequences of the same shuffle)
- Categories covered: **24 / 24** (verified)
- Overlap with Round 1: **0** (verified, and enforced by the script's own assertion)
- Products: see `sampled_product_ids` in `data/output/product_sample_round2_manifest.json` (100 IDs)

### Combined so far

| Round | N   | Seed | Categories covered | Overlap with earlier rounds |
|-------|-----|------|---------------------|------------------------------|
| 1     | 150 | 42   | 24 / 24             | n/a (first round)            |
| 2     | 100 | 7    | 24 / 24             | 0                             |

Pooling both rounds: **250 distinct products**, all 24 `ProductSeries` categories
represented in each round individually (so either round can be used standalone, or
both combined for a larger labeled set).

## Labeling workbook (Excel dropdown)

For each round, `product_sample_round{N}.xlsx` is the file to actually label in. Its
`ProductSeries` column starts **blank** and is restricted to an Excel data-validation
dropdown listing the 24 valid category values (sourced from a hidden `Category List`
sheet) — so a labeler picks from a fixed list instead of typing free text, and Excel
rejects anything that isn't one of the 24 values.

The workbook is deliberately "blind": it does **not** contain the true/original
`ProductSeries` for each product. Those live separately in
`product_sample_round{N}_answer_key.csv` (`ProductId, ProductSeries`), for scoring
labeling accuracy after the fact without the answer being visible while labeling.

## Folder structure

```
llm_product_categorization/
├── README.md
├── scripts/
│   ├── sample_products.py                  # sampling script (source of truth for how each round was drawn)
│   └── make_labeling_workbook.py           # builds the blind .xlsx dropdown workbook + answer key for a round
└── data/
    ├── output/
    │   ├── product_sample_round1.xlsx               # Round 1 labeling workbook: ProductSeries blank + dropdown
    │   ├── product_sample_round1_answer_key.csv      # Round 1: ProductId -> true ProductSeries
    │   ├── product_sample_round1_manifest.json       # Round 1 sampling metadata (seed, method, 150 sampled ProductIds)
    │   ├── product_sample_round2.csv                 # Round 2: 100 products, all 24 ProductSeries covered, true labels included
    │   ├── product_sample_round2.xlsx                # Round 2 labeling workbook: ProductSeries blank + dropdown
    │   ├── product_sample_round2_answer_key.csv      # Round 2: ProductId -> true ProductSeries
    │   └── product_sample_round2_manifest.json       # Round 2 sampling metadata (seed, method, excluded Round 1 IDs, 100 sampled ProductIds)
    └── archive/
        ├── product_sample_100_draft_v1.csv          # superseded: first 100-product plain-random draft
        └── product_sample_100_draft_v1_manifest.json
```

## Reproducing / extending

```powershell
py scripts\sample_products.py             # (re)draw the sample for the configured ROUND
py scripts\make_labeling_workbook.py      # build the .xlsx dropdown workbook + answer key for that round
```

Requires `pandas` and `openpyxl`. Both scripts' config block (`RANDOM_SEED`, `SAMPLE_SIZE`,
`ROUND`) is currently set to Round 2 (100, seed 7); re-running as-is reproduces Round 2
exactly. For a new round:

1. Bump `ROUND` (e.g. to `3`) and set `SAMPLE_SIZE` in both scripts.
2. Pick a new `RANDOM_SEED` (any value not yet used for another round).
3. Run `sample_products.py` — it automatically excludes every `ProductId` from every
   earlier round's manifest already in `data/output/`, and will raise an error if full
   category coverage or zero-overlap can't be guaranteed (e.g. if a category's remaining
   pool runs out, or `SAMPLE_SIZE` is smaller than the number of categories).
4. Run `make_labeling_workbook.py` to produce that round's blind `.xlsx` + answer key.
5. Document the new round in this README (seed, size, coverage, overlap check).

## Provenance

- Round 1 generated: see `created_utc` in `data/output/product_sample_round1_manifest.json`
- Round 2 generated: see `created_utc` in `data/output/product_sample_round2_manifest.json`
- Generated by: teyyubteyyub.mt@gmail.com
