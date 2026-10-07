"""
Draw a reproducible random sample of products from Master_Data_2022_final.csv
for manual/LLM security-category labeling.

Sampling guarantees every ProductSeries category is represented at least once
(the first plain-random 100-product draft missed 3 of 24 series), then fills
the remaining slots randomly. Method:

  1. Exclude any ProductId already used in an earlier round (auto-detected
     from product_sample_round{N}_manifest.json for every N < ROUND already
     in data/output/), so rounds never overlap.
  2. Shuffle the remaining product list once with a fixed random seed.
  3. Walk the shuffled order and take the first product seen for each
     ProductSeries -> guarantees all categories appear, while still being a
     random pick within each category (whichever row the shuffle put first).
  4. Continue down the same shuffled order, taking the next unused rows,
     until SAMPLE_SIZE is reached.

This is equivalent to "keep drawing randomly until every category has at
least one product, then keep drawing until we hit the sample size" but is
deterministic/reproducible given the seed (no rejection-sampling loop).

Usage:
    py scripts/sample_products.py
(edit RANDOM_SEED / SAMPLE_SIZE / ROUND below for a new round)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---- Config -----------------------------------------------------------
RANDOM_SEED = 7
SAMPLE_SIZE = 100
ROUND = 2

SOURCE_CSV = Path(
    r"C:\Users\mutal\OneDrive - University of Tulsa\NSF Proposal\data\output\Master_Data_2022_final.csv"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
SAMPLE_CSV = OUTPUT_DIR / f"product_sample_round{ROUND}.csv"
MANIFEST_JSON = OUTPUT_DIR / f"product_sample_round{ROUND}_manifest.json"

ID_COLUMN = "ProductId"
CATEGORY_COLUMN = "ProductSeries"

KEEP_COLUMNS = ["Round", "ProductId", "VendorName", "Product", "ProductSeries"]


def load_prior_round_ids() -> dict[int, list[int]]:
    """{round_number: [ProductId, ...]} for every earlier round's manifest found on disk."""
    prior = {}
    for manifest_path in OUTPUT_DIR.glob("product_sample_round*_manifest.json"):
        data = json.loads(manifest_path.read_text())
        r = int(data["round"])
        if r < ROUND:
            prior[r] = data["sampled_product_ids"]
    return prior


def main() -> None:
    df = pd.read_csv(SOURCE_CSV, dtype={ID_COLUMN: "Int64"})

    if df[ID_COLUMN].duplicated().any():
        raise ValueError(f"Duplicate {ID_COLUMN} values found in source file; expected unique products.")

    prior_rounds = load_prior_round_ids()
    excluded_ids = sorted({pid for ids in prior_rounds.values() for pid in ids})
    pool = df[~df[ID_COLUMN].isin(excluded_ids)].copy()
    print(f"Excluding {len(excluded_ids)} ProductIds already used in prior round(s): "
          f"{sorted(prior_rounds.keys())} -> pool of {len(pool)} remaining (of {len(df)} total).")

    total_categories = df[CATEGORY_COLUMN].nunique(dropna=True)
    pool_categories = pool[CATEGORY_COLUMN].nunique(dropna=True)
    if pool_categories < total_categories:
        missing = set(df[CATEGORY_COLUMN].unique()) - set(pool[CATEGORY_COLUMN].unique())
        raise AssertionError(
            f"After excluding prior rounds, {total_categories - pool_categories} "
            f"{CATEGORY_COLUMN} categories have NO remaining products: {missing}"
        )
    if SAMPLE_SIZE < total_categories:
        raise ValueError(
            f"SAMPLE_SIZE ({SAMPLE_SIZE}) is smaller than the number of {CATEGORY_COLUMN} "
            f"categories ({total_categories}); full coverage is impossible."
        )

    shuffled = pool.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    coverage_pick = shuffled.drop_duplicates(subset=CATEGORY_COLUMN, keep="first")
    remaining_needed = SAMPLE_SIZE - len(coverage_pick)

    remaining_pool = shuffled[~shuffled[ID_COLUMN].isin(coverage_pick[ID_COLUMN])]
    fill_pick = remaining_pool.head(remaining_needed)

    sample = pd.concat([coverage_pick, fill_pick]).sort_values(ID_COLUMN).reset_index(drop=True)

    missing_categories = set(df[CATEGORY_COLUMN].unique()) - set(sample[CATEGORY_COLUMN].unique())
    if missing_categories:
        raise AssertionError(f"Coverage guarantee failed, missing: {missing_categories}")

    overlap = set(sample[ID_COLUMN]) & set(excluded_ids)
    if overlap:
        raise AssertionError(f"Overlap with prior round(s) detected: {overlap}")

    sample.insert(0, "Round", ROUND)
    sample = sample[KEEP_COLUMNS]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample.to_csv(SAMPLE_CSV, index=False)

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_file": str(SOURCE_CSV),
        "source_row_count": int(len(df)),
        "source_column_count": int(len(df.columns)),
        "sample_size": int(len(sample)),
        "round": ROUND,
        "random_seed": RANDOM_SEED,
        "sampling_method": (
            "Prior-round ProductIds excluded first; full shuffle with fixed seed over the "
            "remaining pool; first occurrence per ProductSeries taken to guarantee category "
            "coverage, then next rows in shuffle order fill the remainder to SAMPLE_SIZE."
        ),
        "id_column": ID_COLUMN,
        "category_column": CATEGORY_COLUMN,
        "total_categories": int(total_categories),
        "categories_covered": int(sample[CATEGORY_COLUMN].nunique()),
        "excluded_prior_rounds": sorted(prior_rounds.keys()),
        "excluded_product_id_count": len(excluded_ids),
        "sampled_product_ids": sample[ID_COLUMN].tolist(),
        "columns": list(sample.columns),
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2))

    print(f"Sampled {len(sample)} of {len(pool)} eligible products (seed={RANDOM_SEED}), round={ROUND}")
    print(f"  categories covered: {sample[CATEGORY_COLUMN].nunique()} / {total_categories}")
    print(f"  overlap with prior rounds: {len(overlap)} (must be 0)")
    print(f"  -> {SAMPLE_CSV}")
    print(f"  -> {MANIFEST_JSON}")


if __name__ == "__main__":
    main()
