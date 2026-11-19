"""
Compares the No DAC baseline runs before and after the offshore wind cost fix
(09c9ac69) and the penalty fix (c347ae62). Reads the technology and network design
from the h5 files of both result folders.
-> data/fixed_owt/technology_comparison.csv, network_comparison.csv, cost_comparison.csv
"""
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

here = Path(__file__).parent
OUT = here / "data" / "fixed_owt"
BASE = Path(r"C:\Users\jwiegner\OneDrive - ETH Zurich\00_Papers_Journal\00_2025-DACOffshore\DAC-Offshore-MaianJan")
RUNS = {
    "old": BASE / "results" / "2040_1",
    "new": BASE / "results_fixedOffshoreWTCost" / "results" / "2040_1",
}
CLIMATE_YEARS = [1995, 2008, 2009]


def find_h5(root, cy):
    files = sorted((root / str(cy) / "No_DAC").glob("*No_DAC_baseline*/optimization_results.h5"))
    return files[-1]


def read_technologies(path):
    rows = []
    with h5py.File(path, "r") as f:
        nodes = f["design/nodes/period1"]
        for node in nodes:
            for tec in nodes[node]:
                d = nodes[node][tec]
                rows.append(dict(node=node, technology=tec, size=d["size"][()].item(),
                                 capex=d["capex_tot"][()].item(), opex_fixed=d["opex_fixed"][()].item(),
                                 opex_variable=d["opex_variable"][()].item(),
                                 unit_capex=d["para_unitCAPEX"][()].item()))
    return pd.DataFrame(rows)


def read_networks(path):
    rows = []
    with h5py.File(path, "r") as f:
        netws = f["design/networks/period1"]
        for netw in netws:
            for arc in netws[netw]:
                d = netws[netw][arc]
                rows.append(dict(network=netw, arc=arc, size=d["size"][()].item(), capex=d["capex"][()].item(),
                                 opex_fixed=d["opex_fixed"][()].item(),
                                 opex_variable=d["opex_variable"][()].item(),
                                 flow=d["total_flow"][()].item()))
    return pd.DataFrame(rows)


tecs, netws = [], []
for version, root in RUNS.items():
    for cy in CLIMATE_YEARS:
        path = find_h5(root, cy)
        print(version, cy, path.parent.name)
        t = read_technologies(path)
        t["version"], t["climate_year"] = version, cy
        tecs.append(t)
        n = read_networks(path)
        n["version"], n["climate_year"] = version, cy
        netws.append(n)

tecs = pd.concat(tecs)
netws = pd.concat(netws)
# Every arc is stored in both directions with the full capex, see analysis_2040.md 5.3
netws["capex"] /= 2
netws["opex_fixed"] /= 2

OUT.mkdir(parents=True, exist_ok=True)
tecs.to_csv(OUT / "technology_design.csv", index=False)
netws.to_csv(OUT / "network_design.csv", index=False)


# --- Cost comparison from the summaries (new Summary.xlsx files hold the old and the new rows) ---
summary = pd.concat(
    [pd.read_excel(f, sheet_name="Summary") for f in sorted(RUNS["new"].glob("*/No_DAC/Summary.xlsx"))])
summary["climate_year"] = summary["case"].str.extract(r"cy(\d{4})")[0].astype(int)
summary["version"] = np.where(summary["time_stamp"].str.contains("/20261111"), "old", "new")
summary["penalty"] = summary["ub"] - summary["total_npv"]
cost_columns = ["total_npv", "cost_capex_tecs", "cost_opex_tecs", "cost_capex_netws", "cost_opex_netws",
                "cost_imports", "carbon_cost", "emissions_pos", "penalty"]
costs = summary.set_index(["climate_year", "version"])[cost_columns].unstack("version")
costs.to_csv(OUT / "cost_comparison.csv")

# --- Figure: change in annualised cost, new - old ---
import matplotlib.pyplot as plt

tecs["cost"] = tecs["capex"] + tecs["opex_fixed"] + tecs["opex_variable"]
netws["cost"] = netws["capex"] + netws["opex_fixed"] + netws["opex_variable"]
groups = {
    "Offshore wind": tecs[tecs.technology == "Offshore_Wind"],
    "Onshore wind": tecs[tecs.technology == "Onshore_Wind"],
    "PV": tecs[tecs.technology == "PV"],
    "Batteries": tecs[tecs.technology.str.startswith("Storage_Battery")],
    "Other technologies": tecs[~tecs.technology.str.match(r"(Offshore_Wind$|Onshore_Wind$|PV$|Storage_Battery)")],
    "Electricity networks": netws,
}
delta = pd.DataFrame({
    name: df.groupby(["climate_year", "version"])["cost"].sum().unstack()
    .pipe(lambda x: (x["new"] - x["old"]) / 1e9)
    for name, df in groups.items()
})
delta["Imports + carbon cost"] = ((costs[("cost_imports", "new")] + costs[("carbon_cost", "new")])
                                 - (costs[("cost_imports", "old")] + costs[("carbon_cost", "old")])) / 1e9
total = (costs[("total_npv", "new")] - costs[("total_npv", "old")]) / 1e9
delta.to_csv(OUT / "cost_change_by_component.csv")

COLORS = ["#2a78d6", "#1baf7a", "#eda100", "#e87ba4", "#9a9a92", "#eb6834", "#5a5a55"]
fig, ax = plt.subplots(figsize=(8, 4.2))
width = 0.11
x = np.arange(len(CLIMATE_YEARS))
for i, (name, color) in enumerate(zip(delta.columns, COLORS)):
    pos = x + (i - (len(delta.columns) - 1) / 2) * (width + 0.01)
    ax.bar(pos, delta[name].values, width, color=color, label=name, zorder=3)
for xi, cy in zip(x, CLIMATE_YEARS):
    ax.text(xi, max(delta.loc[cy].max(), 0) + 0.25, f"Total: {total[cy]:+.2f} bn EUR",
            ha="center", va="bottom", fontsize=9, color="#333333")
ax.axhline(0, color="#555555", lw=0.8, zorder=4)
ax.set_xticks(x, [f"cy {cy}" for cy in CLIMATE_YEARS])
ax.set_ylabel("Change in annual cost, new − old (bn EUR/yr)")
ax.set_ylim(delta.min().min() - 0.5, delta.max().max() + 1.0)
ax.grid(axis="y", color="#e5e5e5", zorder=0)
for side in ["top", "right"]:
    ax.spines[side].set_visible(False)
ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1))
fig.tight_layout()
FIGURES = here / "figures"
fig.savefig(FIGURES / "fig9_baseline_cost_change_fixed_owt.png", dpi=200, bbox_inches="tight")
print(delta.round(3))
print(total.round(3))
print((costs / 1e9).round(3).T)

# --- Circulating flows (what the flow penalty should remove) ---
def get_circulation(path_h5):
    """
    Total electricity flow and circulation, i.e. sum over hours of min(flow i->j, flow j->i)
    (same as extract_run_metrics.get_flow_penalty_metrics; not imported, as that module runs on import)
    """
    total, circulation = 0, 0
    with h5py.File(path_h5, "r") as hdf_file:
        design = hdf_file["design/networks/period1"]
        operation = hdf_file["operation/networks/period1"]
        for network in operation:
            flows = {}
            for arc in operation[network]:
                key = (design[network][arc]["fromNode"][()], design[network][arc]["toNode"][()])
                flows[key] = operation[network][arc]["flow"][:]
            total += sum(flow.sum() for flow in flows.values())
            circulation += sum(np.minimum(flow, flows[(j, i)]).sum()
                               for (i, j), flow in flows.items() if (j, i) in flows and str(i) < str(j))
    return dict(flow_electricity=total, circulation_electricity=circulation)


flow_rows = []
for version, root in RUNS.items():
    for cy in CLIMATE_YEARS:
        flow_rows.append(dict(version=version, climate_year=cy, **get_circulation(find_h5(root, cy))))
flows = pd.DataFrame(flow_rows)
flows.to_csv(OUT / "flow_comparison.csv", index=False)
print(flows)
