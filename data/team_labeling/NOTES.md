# Round 1 Team Labeling — Notes

Three people (Raghavendra, Teyyub, Noah) independently labeled the Round 1
blind workbook (`ProductSeries` chosen from the 24-category dropdown, true
labels withheld). Two versions of the combined workbook are kept here:

- **`round1_team_labeling_v1_initial.xlsx`** — everyone's first pass, done
  independently before any group discussion.
- **`round1_team_labeling_v2_post_discussion.xlsx`** — the same 150 products,
  revisited after the group talked through disagreements and ambiguous
  categories. Adds a `Vertical?` column and an `AllCategories` discussion
  sheet (see below); `AnswerKey` is unchanged between versions.

Both files have one sheet per labeler (`LabelingRaghavendra`,
`LabelingTeyyub`, `LabelingNoah`), plus `AnswerKey` (true `ProductSeries`,
for scoring), `AllCategories` (category-definition discussion, v2 only), and
`Category List` (the 24 valid values, used for the dropdown).

## What changed between v1 and v2

Comparing each labeler's primary `ProductSeries` column, row by row:

| Labeler      | Labels changed | Filled in, v1 → v2 | Exact-match accuracy vs AnswerKey, v1 → v2 |
|--------------|----------------|---------------------|----------------------------------------------|
| Raghavendra  | 62 / 150       | 139 → 148           | 27.3% → 38.5%                                 |
| Teyyub       | 2 / 150        | 150 → 150           | 58.0% → 56.7%                                 |
| Noah         | 87 / 150       | 81 → 145            | 24.7% → 37.2%                                 |

Takeaways:

- The group discussion drove a real, substantial revision for two of the
  three labelers (Raghavendra and Noah each changed 40-60% of their labels),
  not just a handful of edge cases.
- It also closed most of the completion gap: Noah went from 81 to 145 of 150
  products labeled; Raghavendra from 139 to 148.
- Accuracy against the single-answer `AnswerKey` rose accordingly for
  Raghavendra and Noah (both gained ~11-12 points). Teyyub was already the
  most accurate of the three in v1 and stayed essentially flat (changed only
  2 labels).
- **Caveat on "accuracy":** `AnswerKey` records one `ProductSeries` per
  product, but several categories genuinely overlap (see below), so a
  mismatch against `AnswerKey` isn't always a labeling error — sometimes
  it's a defensible alternative category. The accuracy numbers above are a
  useful signal of convergence, not a ground-truth pass/fail rate.

## Category ambiguity raised in discussion (`AllCategories` sheet, v2)

Free-text notes left against specific categories while reviewing the full
24-category list — mostly candidates for merging or clearer boundary rules:

- **IT Development/Infrastructure** — "might include server[s]", "includes
  device management"; **Web Tools & Plugins** noted as effectively a subset
  of it.
- **Sales** — **Retail & Digital Commerce** noted as "a subset of this."
- **Data Management Business Intelligence & Analytics** — "also includes
  storage management"; **Storage** noted as overlapping.
- **Marketing** — **Advertising** noted as "a subset of this."
- **Financial Management & GRC** — note to consider "dividing GRC and
  finance" into separate categories rather than one combined bucket.
- **IT Security Information** — "can be combined with network monitoring";
  i.e. overlaps **Network Security Monitoring**.
- **Other** — examples surfaced that didn't fit elsewhere: "Medical", "event
  management".

None of these were actually merged yet (the `New Categories` column in that
sheet is effectively a copy of the current 24, not a finalized new list) —
this is an open discussion captured for whoever next revises the taxonomy,
not a decision that's been made.

## New in v2: the `Vertical?` column

A `yes`/blank flag added to each labeler's sheet, orthogonal to
`ProductSeries` — marks products that are specific to a particular industry
("vertical") rather than a horizontal product category (e.g. SAP Aerospace &
Defense: Raghavendra flagged `Vertical? = yes` while also assigning it a
regular `ProductSeries`). This looks like an attempt to separate "what kind
of product is this" from "is it industry-specific," since `Verticals` as a
single catch-all `ProductSeries` value was one of the harder categories for
labelers to agree on (e.g. ProductId 358 above: Raghavendra →
`Enterprise Business Solution`, Teyyub → `Verticals`, Noah →
`Data Management Business Intelligence & Analytics` — three different
primary-category guesses for the same product).

## Not included here

- `product_sample_round1 (2).xlsx` (from Downloads) is a byte-identical
  duplicate of v2 (same MD5) — skipped, nothing to add.
- The standalone per-person CSVs in Downloads
  (`product_sample_round1(LabelingRaghavendra).csv`,
  `product_sample_round1(LabelingTeyyub).csv`) weren't pulled in since the
  same data already lives in both xlsx workbooks above — say the word if you
  want them archived here too.
