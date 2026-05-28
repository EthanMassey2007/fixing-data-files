import os
import unicodedata
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "data")

cases_file = os.path.join(data_dir, "cases.csv")
temperature_file = os.path.join(data_dir, "temperature.csv")
humidity_file = os.path.join(data_dir, "humidity.csv")
rainfall_file = os.path.join(data_dir, "rainfall.csv")
population_file = os.path.join(data_dir, "population.csv")
idhm_file = os.path.join(data_dir, "idhm.csv")

TARGET_YEAR = 2018
TARGET_WEEKS = list(range(30, 38))


def normalize_name(name):
    if not isinstance(name, str):
        return ""
    return unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII").lower().strip()


def fetch_dengue_row(municipio, week, year):
    api_url = "https://info.dengue.mat.br/api/alertcity"

    params = {
        "geocode": municipio["geocode"],
        "disease": "dengue",
        "format": "json",
        "ew_start": week,
        "ew_end": week,
        "ey_start": year,
        "ey_end": year,
    }

    name = normalize_name(municipio["name"])

    try:
        r = requests.get(api_url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        if not data:
            return {
                "municipio": name,
                "year": year,
                "week": week,
                "cases": 0,
                "temperature": 0,
                "humidity": 0,
            }

        row = data[0]

        return {
            "municipio": name,
            "year": year,
            "week": week,
            "cases": int(row.get("casos") or 0),
            "temperature": float(row.get("tempmed") or 0),
            "humidity": float(row.get("umidmed") or 0),
        }

    except Exception as e:
        print(f"Failed: {name}, {year} week {week}: {e}")
        return None


def replace_rows(csv_file, value_column, new_rows):
    df = pd.read_csv(csv_file)
    df.columns = [c.strip().lower() for c in df.columns]
    df["municipio"] = df["municipio"].apply(normalize_name)

    replacement = pd.DataFrame(
        [
            {
                "municipio": r["municipio"],
                "year": r["year"],
                "week": r["week"],
                value_column: r[value_column],
            }
            for r in new_rows
        ]
    )

    bad_mask = (df["year"] == TARGET_YEAR) & (df["week"].isin(TARGET_WEEKS))
    df = df[~bad_mask].copy()

    df = pd.concat([df, replacement], ignore_index=True)
    df = df.sort_values(["municipio", "year", "week"]).reset_index(drop=True)

    df.to_csv(csv_file, index=False)
    print(f"Updated {csv_file}")


def repair_static_file(csv_file, value_column):
    df = pd.read_csv(csv_file)
    df.columns = [c.strip().lower() for c in df.columns]
    df["municipio"] = df["municipio"].apply(normalize_name)

    fixed_rows = []

    for municipio in sorted(df["municipio"].unique()):
        good_rows = df[
            (df["municipio"] == municipio)
            & ~((df["year"] == TARGET_YEAR) & (df["week"].isin(TARGET_WEEKS)))
        ]

        if good_rows.empty:
            continue

        value = good_rows[value_column].dropna().iloc[0]

        for week in TARGET_WEEKS:
            fixed_rows.append(
                {
                    "municipio": municipio,
                    "year": TARGET_YEAR,
                    "week": week,
                    value_column: value,
                }
            )

    bad_mask = (df["year"] == TARGET_YEAR) & (df["week"].isin(TARGET_WEEKS))
    df = df[~bad_mask].copy()

    df = pd.concat([df, pd.DataFrame(fixed_rows)], ignore_index=True)
    df = df.sort_values(["municipio", "year", "week"]).reset_index(drop=True)

    df.to_csv(csv_file, index=False)
    print(f"Updated {csv_file}")


def main():
    ibge_url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/33/municipios"
    municipalities = requests.get(ibge_url, timeout=20).json()

    municipalities_info = [
        {
            "name": m["nome"],
            "geocode": m["id"],
        }
        for m in municipalities
    ]

    new_rows = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        for year in [TARGET_YEAR]:
            for week in TARGET_WEEKS:
                for municipio in municipalities_info:
                    futures.append(executor.submit(fetch_dengue_row, municipio, week, year))

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                new_rows.append(result)

    replace_rows(cases_file, "cases", new_rows)
    replace_rows(temperature_file, "temperature", new_rows)
    replace_rows(humidity_file, "humidity", new_rows)

    repair_static_file(population_file, "population")
    repair_static_file(idhm_file, "idhm")

    print("Done fixing 2018 weeks 30-37.")


if __name__ == "__main__":
    main()