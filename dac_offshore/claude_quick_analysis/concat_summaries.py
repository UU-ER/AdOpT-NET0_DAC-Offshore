import re
from pathlib import Path

import pandas as pd

# Root folder containing <climate_year>/<case_type>/Summary.xlsx and the result folders
ROOT_PATH = Path(
    r"C:\Users\jwiegner\OneDrive - ETH Zurich\00_Papers_Journal\00_2025-DACOffshore\DAC-Offshore-MaianJan\results\2040_1"
)

SUMMARY_SHEET = "Summary"
OUTPUT_FILE = Path(__file__).parent / "data" / "Summary_2040_processed.csv"

# Case prefix -> DAC configuration. Order matters:
# "DAC" must be checked last, as it is contained in the other prefixes.
CASE_TYPES = [
    ("No_DAC", "No DAC"),
    ("Offshore_DAC_only", "DAC offshore"),
    ("Onshore_DAC_only", "DAC onshore"),
    ("DAC", "DAC"),
]


def get_dac_configuration(case):
    for prefix, label in CASE_TYPES:
        if case.startswith(prefix):
            return label
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


def get_result_path(summary_file, euler_time_stamp):
    # The time_stamp column contains the euler path, the last folder is the result folder
    folder_name = Path(euler_time_stamp).name
    path = summary_file.parent / folder_name
    if not path.exists():
        print(f"Warning: result folder not found: {path}")
    return str(path)


# Read all summary files and append them to one dataframe
summaries = []
for summary_file in sorted(ROOT_PATH.glob("*/*/Summary.xlsx")):
    summary = pd.read_excel(summary_file, sheet_name=SUMMARY_SHEET)
    summary["result_path"] = [
        get_result_path(summary_file, time_stamp) for time_stamp in summary["time_stamp"]
    ]
    summaries.append(summary)
    print(f"Read {summary_file} ({len(summary)} rows)")

summary = pd.concat(summaries, ignore_index=True)

summary["dac_configuration"] = summary["case"].apply(get_dac_configuration)
summary["emission_target"] = summary["case"].apply(get_emission_target)
summary["climate_year"] = summary["case"].apply(get_climate_year)

# Specific capture costs: additional cost compared to the No DAC case of the
# same climate year, divided by the negative emissions
no_dac_cost = summary[summary["dac_configuration"] == "No DAC"].set_index(
    "climate_year"
)["total_npv"]
additional_cost = summary["total_npv"] - summary["climate_year"].map(no_dac_cost)
summary["specific_capture_cost"] = additional_cost / summary["emissions_neg"].where(
    summary["emissions_neg"] > 0
)

summary = summary.sort_values(["climate_year", "dac_configuration", "emission_target"])

OUTPUT_FILE.parent.mkdir(exist_ok=True)
summary.to_csv(OUTPUT_FILE, index=False)
print(f"Saved {OUTPUT_FILE}")
