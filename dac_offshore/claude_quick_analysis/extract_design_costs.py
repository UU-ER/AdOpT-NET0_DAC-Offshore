"""
Size and annualised costs of every technology and network arc per run, from the design part
of the h5 files only (fast). Run concat_summaries.py first.
-> data/design_costs.csv (case, kind, network, node_or_arc, technology, size, capex, opex_fixed, opex_variable)
"""
import os
from pathlib import Path

import h5py
import pandas as pd

here = Path(__file__).parent
# QA_OUTPUT_DIR: folder with data/ and figures/ (default: this folder)
out = Path(os.environ.get("QA_OUTPUT_DIR", here))
SUMMARY_FILE = out / "data" / "Summary_2040_processed.csv"
OUTPUT_FILE = out / "data" / "design_costs.csv"


def value(dataset):
    return float(dataset[()].sum())


def read_design(path_h5):
    rows = []
    with h5py.File(path_h5, "r") as hdf_file:
        nodes = hdf_file["design/nodes/period1"]
        for node in nodes:
            for technology in nodes[node]:
                design = nodes[node][technology]
                rows.append(dict(kind="technology", node=node, technology=technology,
                                 size=value(design["size"]), capex=value(design["capex_tot"]),
                                 opex_fixed=value(design["opex_fixed"]),
                                 opex_variable=value(design["opex_variable"])))
        networks = hdf_file["design/networks/period1"]
        for network in networks:
            for arc in networks[network]:
                design = networks[network][arc]
                rows.append(dict(kind="network", node=f"{design['fromNode'][()].decode()}-{design['toNode'][()].decode()}"
                                 if isinstance(design["fromNode"][()], bytes) else arc,
                                 technology=network, size=value(design["size"]), capex=value(design["capex"]),
                                 opex_fixed=value(design["opex_fixed"]),
                                 opex_variable=value(design["opex_variable"])))
    return pd.DataFrame(rows)


summary = pd.read_csv(SUMMARY_FILE)
designs = []
for _, run in summary.iterrows():
    path_h5 = Path(run["result_path"]) / "optimization_results.h5"
    if not path_h5.exists():
        print(f"Skipping {run['case']}: no h5 file")
        continue
    print(f"Reading {run['case']}")
    design = read_design(path_h5)
    design["case"] = run["case"]
    designs.append(design)

design = pd.concat(designs, ignore_index=True)
design.to_csv(OUTPUT_FILE, index=False)
print(f"Saved {OUTPUT_FILE}")
