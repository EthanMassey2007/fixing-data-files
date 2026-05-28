import os
import pandas as pd
import numpy as np

base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "data")

input_file = os.path.join(data_dir, "combined_data.csv")
output_file = os.path.join(data_dir, "combined_data_nan.csv")


def main():
    df = pd.read_csv(input_file)
    df.columns = [c.strip().lower() for c in df.columns]

    required_columns = {"temperature", "humidity"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
    df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce")

    temp_zero_count = int((df["temperature"] == 0).sum())
    humidity_zero_count = int((df["humidity"] == 0).sum())

    df.loc[df["temperature"] == 0, "temperature"] = np.nan
    df.loc[df["humidity"] == 0, "humidity"] = np.nan

    df.to_csv(output_file, index=False)

    print(f"Saved cleaned file to: {output_file}")
    print(f"Temperature zeros changed to NaN: {temp_zero_count}")
    print(f"Humidity zeros changed to NaN: {humidity_zero_count}")
    print(f"Remaining temperature zeros: {int((df['temperature'] == 0).sum())}")
    print(f"Remaining humidity zeros: {int((df['humidity'] == 0).sum())}")


if __name__ == "__main__":
    main()