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

rainfall_source_file = os.path.join(data_dir, "bra-rainfall-subnat-full.csv")
pcode_file = os.path.join(data_dir, "global_pcodes.csv")

TARGET_RANGES = [
    (2018, list(range(30, 38))),
    (2025, list(range(43, 53))),
]

name_corrections = {
    "Parati": "Paraty",
    "Niteroi": "Niterói",
    "Sao Goncalo": "São Gonçalo",
    "Nova Iguacu": "Nova Iguaçu",
    "Mesquita": "Mesquita",
    "Rio de Janeiro": "Rio de Janeiro",
    "Trajano de Morais": "Trajano de Moraes",
    "Areal": "Areal",
}


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


def is_target_row(df):
    mask = pd.Series(False, index=df.index)

    for year, weeks in TARGET_RANGES:
        mask |= (df["year"] == year) & (df["week"].isin(weeks))

    return mask


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
        print(f"Failed API fetch: {name}, {year} week {week}: {e}")
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

    df = df[~is_target_row(df)].copy()

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
        for year, weeks in TARGET_RANGES:
            good_rows = df[
                (df["municipio"] == municipio)
                & ~((df["year"] == year) & (df["week"].isin(weeks)))
            ]

            if good_rows.empty:
                continue

            value = good_rows[value_column].dropna().iloc[-1]

            for week in weeks:
                fixed_rows.append(
                    {
                        "municipio": municipio,
                        "year": year,
                        "week": week,
                        value_column: value,
                    }
                )

    df = df[~is_target_row(df)].copy()

    df = pd.concat([df, pd.DataFrame(fixed_rows)], ignore_index=True)
    df = df.sort_values(["municipio", "year", "week"]).reset_index(drop=True)

    df.to_csv(csv_file, index=False)
    print(f"Updated {csv_file}")


def load_rainfall_sources():
    rainfall_df = pd.read_csv(rainfall_source_file)
    pcode_df = pd.read_csv(pcode_file, low_memory=False)

    rainfall_df.columns = [c.strip() for c in rainfall_df.columns]
    pcode_df.columns = [c.strip() for c in pcode_df.columns]

    required_rainfall_cols = {"PCODE", "date", "rfh_avg"}
    required_pcode_cols = {"Parent P-Code", "P-Code", "Name"}

    missing_rainfall = required_rainfall_cols - set(rainfall_df.columns)
    missing_pcode = required_pcode_cols - set(pcode_df.columns)

    if missing_rainfall:
        raise ValueError(f"Rainfall source missing columns: {missing_rainfall}")

    if missing_pcode:
        raise ValueError(f"P-code file missing columns: {missing_pcode}")

    municipalities_df = pcode_df[pcode_df["Parent P-Code"] == "BR33"][
        ["P-Code", "Name"]
    ].copy()

    municipalities_df.rename(
        columns={
            "Name": "MUNICIPIO",
            "P-Code": "PCODE",
        },
        inplace=True,
    )

    rainfall_df["DATE"] = pd.to_datetime(rainfall_df["date"], errors="coerce")
    rainfall_df["PRECIP"] = (
        pd.to_numeric(rainfall_df["rfh_avg"], errors="coerce").fillna(0) / 10.0
    )
    rainfall_df = rainfall_df.dropna(subset=["DATE"])

    return rainfall_df, municipalities_df


def weekly_rainfall(year, week, rainfall_df, municipalities_df):
    week_sum = {}

    for _, row in municipalities_df.iterrows():
        muni_raw = row["MUNICIPIO"]
        muni_corrected = name_corrections.get(muni_raw, muni_raw)
        muni_name = normalize_name(muni_corrected)

        muni_rain = rainfall_df[rainfall_df["PCODE"] == row["PCODE"]].copy()

        week_precip = 0.0

        for _, r in muni_rain.iterrows():
            for day_offset in range(10):
                day = r["DATE"] + pd.Timedelta(days=day_offset)

                if day.year == year and day.isocalendar()[1] == week:
                    week_precip += r["PRECIP"]

        week_sum[muni_name] = week_precip

    return week_sum


def build_rainfall_rows():
    rainfall_df, municipalities_df = load_rainfall_sources()

    rows = []

    for year, weeks in TARGET_RANGES:
        for week in weeks:
            print(f"Computing rainfall for {year} week {week}...")
            rain_dict = weekly_rainfall(year, week, rainfall_df, municipalities_df)

            for municipio, rainfall in rain_dict.items():
                rows.append(
                    {
                        "municipio": municipio,
                        "year": year,
                        "week": week,
                        "rainfall": rainfall,
                    }
                )

    return rows


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

        for year, weeks in TARGET_RANGES:
            for week in weeks:
                for municipio in municipalities_info:
                    futures.append(
                        executor.submit(fetch_dengue_row, municipio, week, year)
                    )

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                new_rows.append(result)

    replace_rows(cases_file, "cases", new_rows)
    replace_rows(temperature_file, "temperature", new_rows)
    replace_rows(humidity_file, "humidity", new_rows)

    rainfall_rows = build_rainfall_rows()
    replace_rows(rainfall_file, "rainfall", rainfall_rows)

    repair_static_file(population_file, "population")
    repair_static_file(idhm_file, "idhm")

    print("Done fixing 2018 weeks 30-37 and 2025 weeks 43-52.")


if __name__ == "__main__":
    main()