import os
import pandas as pd
import unicodedata

base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "data")

cases_file = os.path.join(data_dir, "cases.csv")
humidity_file = os.path.join(data_dir, "humidity.csv")
idhm_file = os.path.join(data_dir, "idhm.csv")
population_file = os.path.join(data_dir, "population.csv")
rainfall_file = os.path.join(data_dir, "rainfall.csv")
temperature_file = os.path.join(data_dir, "temperature.csv")

output_file = os.path.join(data_dir, "combined_data.csv")

KEYS = ["municipio", "year", "week"]


def normalize_name(name):
    if not isinstance(name, str):
        return ""
    return unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII").lower().strip()


def load_dataset(file_path, value_column):
    df = pd.read_csv(file_path)
    df.columns = [c.strip().lower() for c in df.columns]

    required_columns = KEYS + [value_column]
    missing_columns = [c for c in required_columns if c not in df.columns]

    if missing_columns:
        raise ValueError(f"{file_path} is missing columns: {missing_columns}")

    df = df[required_columns].copy()

    df["municipio"] = df["municipio"].apply(normalize_name)
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    df["week"] = pd.to_numeric(df["week"], errors="raise").astype(int)
    df[value_column] = pd.to_numeric(df[value_column], errors="raise")

    duplicates = df[df.duplicated(KEYS, keep=False)]
    if not duplicates.empty:
        raise ValueError(
            f"{file_path} has duplicate rows for the same municipio/year/week:\n"
            f"{duplicates.head(20)}"
        )

    return df


def main():
    cases_df = load_dataset(cases_file, "cases")
    humidity_df = load_dataset(humidity_file, "humidity")
    idhm_df = load_dataset(idhm_file, "idhm")
    population_df = load_dataset(population_file, "population")
    rainfall_df = load_dataset(rainfall_file, "rainfall")
    temperature_df = load_dataset(temperature_file, "temperature")

    combined = cases_df

    datasets = [
        (humidity_df, "humidity"),
        (idhm_df, "idhm"),
        (population_df, "population"),
        (rainfall_df, "rainfall"),
        (temperature_df, "temperature"),
    ]

    for df, name in datasets:
        before_rows = len(combined)

        combined = combined.merge(
            df,
            on=KEYS,
            how="inner",
            validate="one_to_one",
        )

        after_rows = len(combined)

        if after_rows != before_rows:
            raise ValueError(
                f"Merge with {name} changed row count from {before_rows} to {after_rows}. "
                f"That means some municipio/year/week rows do not match across files."
            )

    expected_rows = len(cases_df)

    if len(combined) != expected_rows:
        raise ValueError(
            f"Final combined dataset has {len(combined)} rows, but cases.csv has {expected_rows} rows."
        )

    if combined.isna().any().any():
        missing = combined.columns[combined.isna().any()].tolist()
        raise ValueError(f"Combined file contains missing values in columns: {missing}")

    combined = combined.sort_values(["municipio", "year", "week"]).reset_index(drop=True)

    combined.to_csv(output_file, index=False)

    print(f"Combined CSV saved to: {output_file}")
    print(f"Rows: {len(combined)}")
    print(f"Columns: {list(combined.columns)}")


if __name__ == "__main__":
    main()