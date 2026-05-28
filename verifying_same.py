import os
import unicodedata
import pandas as pd

base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "data")

combined_file = os.path.join(data_dir, "combined_data.csv")

files = {
    "cases": os.path.join(data_dir, "cases.csv"),
    "humidity": os.path.join(data_dir, "humidity.csv"),
    "idhm": os.path.join(data_dir, "idhm.csv"),
    "population": os.path.join(data_dir, "population.csv"),
    "rainfall": os.path.join(data_dir, "rainfall.csv"),
    "temperature": os.path.join(data_dir, "temperature.csv"),
}

KEYS = ["municipio", "year", "week"]


def normalize_name(name):
    if not isinstance(name, str):
        return ""
    return unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII").lower().strip()


def load_file(path, value_column=None):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    df["municipio"] = df["municipio"].apply(normalize_name)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["week"] = pd.to_numeric(df["week"], errors="coerce").astype("Int64")

    if value_column is not None:
        df[value_column] = pd.to_numeric(df[value_column], errors="coerce")

    return df


def print_time_range(label, df):
    if df.empty:
        print(f"  {label}: none")
        return

    ordered = df.dropna(subset=["year", "week"]).sort_values(["year", "week"])

    if ordered.empty:
        print(f"  {label}: none")
        return

    earliest = ordered.iloc[0]
    latest = ordered.iloc[-1]

    print(f"  Earliest {label}: year {int(earliest['year'])}, week {int(earliest['week'])}")
    print(f"  Latest {label}: year {int(latest['year'])}, week {int(latest['week'])}")


def main():
    combined = load_file(combined_file)

    total_conflicts = 0

    print("Checking combined_data.csv against individual CSV files...\n")

    for column, path in files.items():
        original = load_file(path, column)

        needed_cols = KEYS + [column]
        original = original[needed_cols].copy()
        combined_subset = combined[needed_cols].copy()

        merged = combined_subset.merge(
            original,
            on=KEYS,
            how="outer",
            suffixes=("_combined", "_original"),
            indicator=True,
        )

        missing_from_original = merged[merged["_merge"] == "left_only"]
        missing_from_combined = merged[merged["_merge"] == "right_only"]

        both = merged[merged["_merge"] == "both"].copy()

        combined_col = f"{column}_combined"
        original_col = f"{column}_original"

        conflicts = both[
            (both[combined_col].round(10) != both[original_col].round(10))
            & ~(both[combined_col].isna() & both[original_col].isna())
        ]

        conflict_count = len(conflicts)
        total_conflicts += conflict_count

        print(f"{column}:")
        print(f"  Conflicting values: {conflict_count}")
        print_time_range("conflict", conflicts)

        print(f"  Rows missing from original file: {len(missing_from_original)}")
        print_time_range("missing from original", missing_from_original)

        print(f"  Rows missing from combined file: {len(missing_from_combined)}")
        print_time_range("missing from combined", missing_from_combined)

        if conflict_count > 0:
            print("  First conflicts:")
            print(
                conflicts[
                    KEYS + [combined_col, original_col]
                ].head(10).to_string(index=False)
            )

        print()

    print(f"Total conflicting rows across all columns: {total_conflicts}")


if __name__ == "__main__":
    main()