"""
Annual sums of the main technology operation variables per run, node and technology, plus
hourly load statistics of the DAC units (run concat_summaries.py first).
-> data/node_operation.csv (long format: case, node, technology, variable, value)
"""
import os
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

here = Path(__file__).parent
# QA_OUTPUT_DIR: folder with data/ and figures/ (default: this folder)
out = Path(os.environ.get("QA_OUTPUT_DIR", here))
SUMMARY_FILE = out / "data" / "Summary_2040_processed.csv"
OUTPUT_FILE = out / "data" / "node_operation.csv"

VARIABLES = ["electricity_output", "electricity_input", "curtailment_electricity", "heat_output",
             "heat_input", "ohmic_heating", "CO2captured_output", "CO2captured_input", "gas_input"]


def read_node_operation(path_h5):
    rows = []
    with h5py.File(path_h5, "r") as hdf_file:
        operation = hdf_file["operation/technology_operation/period1"]
        for node in operation:
            for technology in operation[node]:
                tec_operation = operation[node][technology]
                for variable in VARIABLES:
                    if variable in tec_operation:
                        rows.append((node, technology, variable, tec_operation[variable][:].sum()))
                if technology.startswith("DAC_Adsorption") and "max_out" in tec_operation:
                    max_out = tec_operation["max_out"][:]
                    if max_out.max() > 1:
                        load = tec_operation["CO2captured_output"][:] / max_out
                        rows.append((node, technology, "hours_below_half_load", (load < 0.5).sum()))
                        rows.append((node, technology, "max_out", max_out.sum()))
    return pd.DataFrame(rows, columns=["node", "technology", "variable", "value"])


summary = pd.read_csv(SUMMARY_FILE)
operations = []
for _, run in summary.iterrows():
    path_h5 = Path(run["result_path"]) / "optimization_results.h5"
    if not path_h5.exists():
        print(f"Skipping {run['case']}: no h5 file")
        continue
    print(f"Reading {run['case']}")
    operation = read_node_operation(path_h5)
    operation["case"] = run["case"]
    operations.append(operation)

operation = pd.concat(operations, ignore_index=True)
operation.to_csv(OUTPUT_FILE, index=False)
print(f"Saved {OUTPUT_FILE}")
