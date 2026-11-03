import re
from pathlib import Path

import pandas as pd

# Root folder containing Summary.xlsx and the case result folders
ROOT_PATH = Path(
    r"C:\Users\jwiegner\OneDrive - ETH Zurich\00_Papers_Journal\00_2025-DACOffshore\DAC-Offshore-MaianJan\cy1995"
)

SUMMARY_FILE = ROOT_PATH / "Summary.xlsx"
SUMMARY_SHEET = "Summary"
OUTPUT_FILE = ROOT_PATH / "Summary_processed.csv"

# Case prefix -> (DAC configuration, subfolder in ROOT_PATH). Order matters:
# "DAC_" must be checked last, as it is contained in the other prefixes.
CASE_TYPES = [
    ("No_DAC", "No DAC", None),
    ("Offshore_DAC_only", "DAC offshore", "Offshore_DAC_only"),
    ("Onshore_DAC_only", "DAC onshore", "Onshore_DAC_only"),
    ("DAC", "DAC", "DAC"),
]


def get_dac_configuration(case):
    for prefix, label, subfolder in CASE_TYPES:
        if case.startswith(prefix):
            return label, subfolder
    raise ValueError(f"Unknown case type: {case}")


def get_emission_target(case):
    if case.startswith("No_DAC"):
        return "none"
    if "max_neg_E" in case:
        return "max"
    match = re.search(r"neg_E_(\d+)pct", case)
    if match:
        return f"{match.group(1)}%"
    raise ValueError(f"Unknown emission target: {case}")


def get_climate_year(case):
    match = re.search(r"cy(\d{4})", case)
    if match:
        return int(match.group(1))
    raise ValueError(f"Unknown climate year: {case}")


def get_result_path(case, subfolder):
    # Result folders are named like the case, without the run suffix
    folder_name = case.replace("_netsplit_oldloss", "")
    if subfolder is None:
        path = ROOT_PATH / folder_name
    else:
        path = ROOT_PATH / subfolder / folder_name
    if not path.exists():
        print(f"Warning: result folder not found: {path}")
    return str(path)


summary = pd.read_excel(SUMMARY_FILE, sheet_name=SUMMARY_SHEET)

configurations = summary["case"].apply(get_dac_configuration)
summary["dac_configuration"] = configurations.str[0]
summary["emission_target"] = summary["case"].apply(get_emission_target)
summary["climate_year"] = summary["case"].apply(get_climate_year)
summary["time_stamp"] = [
    get_result_path(case, subfolder)
    for case, subfolder in zip(summary["case"], configurations.str[1])
]

# Specific capture costs: additional cost compared to the No DAC case of the
# same climate year, divided by the negative emissions
no_dac_cost = summary[summary["dac_configuration"] == "No DAC"].set_index(
    "climate_year"
)["total_npv"]
additional_cost = summary["total_npv"] - summary["climate_year"].map(no_dac_cost)
summary["specific_capture_cost"] = additional_cost / summary["emissions_neg"].where(
    summary["emissions_neg"] > 0
)

summary.to_csv(OUTPUT_FILE, index=False)
print(f"Saved {OUTPUT_FILE}")
