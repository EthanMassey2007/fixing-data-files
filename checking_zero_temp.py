import os
import pandas as pd
import unicodedata

base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "data")

combined_file = os.path.join(data_dir, "temperature.csv")


def normalize_name(name):
    if not isinstance(name, str):
        return ""
    return (
        unicodedata.normalize("NFKD", name)
        .encode("ASCII", "ignore")
        .decode("ASCII")
        .lower()
        .strip()
    )


def main():
    df = pd.read_csv(combined_file)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"municipio", "year", "week", "temperature"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"combined_data.csv is missing columns: {missing}")

    df["municipio"] = df["municipio"].apply(normalize_name)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")

    zero_df = df[df["temperature"] == 0].copy()

    municipalities = sorted(zero_df["municipio"].dropna().unique())

    print(f"Municipalities with temperature = 0 at least once: {len(municipalities)}")
    print()

    if zero_df.empty:
        print("No zero-temperature rows found.")
        return

    summary = (
        zero_df.sort_values(["municipio", "year", "week"])
        .groupby("municipio")
        .agg(
            zero_rows=("temperature", "size"),
            first_year=("year", "first"),
            first_week=("week", "first"),
            latest_year=("year", "last"),
            latest_week=("week", "last"),
        )
        .reset_index()
        .sort_values(["zero_rows", "municipio"], ascending=[False, True])
    )

    print(summary.to_string(index=False))

    output_file = os.path.join(data_dir, "zero_temperature_summary.csv")
    summary.to_csv(output_file, index=False)

    print()
    print(f"Saved summary to: {output_file}")


if __name__ == "__main__":
    main()