Dataset README
Download bra-rainfall-subnat-full.csv here:
https://data.humdata.org/dataset/bra-rainfall-subnational/resource/373e773f-58e3-487e-b219-f566ece64d5e

Overview

This folder contains a collection of raw data files along with a cleaned and consolidated dataset:

combined_data.csv

The original data files contained a small number of faulty or inconsistent rows. These issues have been corrected in combined_data.csv, which merges all source files into a single cleaned dataset.

Files
Raw Data Files

The original files are included for reference and archival purposes. These files may contain:

Faulty rows
Missing or inconsistent values
Formatting inconsistencies
combined_data.csv

This is the recommended dataset to use.

It:

Combines all original data files into a single CSV
Removes or fixes known faulty rows
Standardizes formatting across files
Provides a cleaner dataset for analysis and modeling
Notes
Users should prefer combined_data.csv over the raw files unless reproducing the original preprocessing pipeline.
The cleaning process only addressed rows identified as faulty; all other data was preserved as closely as possible to the originals.
Usage

Example (Python with pandas):

import pandas as pd

df = pd.read_csv("combined_data.csv")

print(df.head())
Purpose

The consolidated dataset was created to simplify downstream analysis and ensure consistent, reliable data across all records.