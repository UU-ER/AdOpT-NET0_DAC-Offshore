"""
Figures and tables for analysis_2040_emission_reduction_target.md. Run concat_summaries.py,
extract_design_costs.py and extract_node_operation.py first (with the same QA_OUTPUT_DIR).
- Average capture cost per configuration and climate year
- Capture cost by technology group (from the h5 design, cross-checked with the summary)
- DAC electricity demand per tonne and cost of the additional electricity supply per MWh
"""
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

here = Path(__file__).parent
# QA_OUTPUT_DIR: folder with data/ and figures/ (default: this folder)
out = Path(os.environ.get("QA_OUTPUT_DIR", here))
data_dir = out / "data"
figure_dir = out / "figures"
figure_dir.mkdir(exist_ok=True)

COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
GREY = "#52514e"
# Configuration -> (color, marker); markers keep the lines apart without color
CONFIGURATIONS = {
    "DAC": (COLORS[0], "o"),
    "DAC onshore": (COLORS[1], "s"),
    "DAC offshore": (COLORS[2], "^"),
}
TECHNOLOGY_GROUPS = {
    "DAC_Adsorption": "DAC",
    "HeatPump": "Heat pumps",
    "PermanentStorage": "CO2 transport & storage",
    "Onshore_Wind": "Onshore wind",
    "Offshore_Wind": "Offshore wind",
    "PV": "PV",
    "Storage_Battery": "Batteries",
}
GROUP_COLORS = {
    "DAC": COLORS[0],
    "Heat pumps": COLORS[1],
    "CO2 transport & storage": COLORS[2],
    "Onshore wind": COLORS[3],
    "Offshore wind": COLORS[4],
    "PV": COLORS[5],
    "Batteries": COLORS[6],
    "Electricity networks": "#9a9a9a",
}
ELECTRICITY_GROUPS = ["Onshore wind", "Offshore wind", "PV", "Batteries", "Electricity networks"]

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": "#e5e5e5",
    "axes.axisbelow": True,
})


def get_group(kind, technology):
    if kind == "network":
        return "CO2 transport & storage" if technology == "CO2_Pipeline" else "Electricity networks"
    for prefix, group in TECHNOLOGY_GROUPS.items():
        if technology.startswith(prefix):
            return group
    return "Other"


def get_costs_by_group(summary, design):
    """
    Annualised cost (CAPEX + fixed and variable OPEX) per group and run. Electricity arcs
    are saved in both directions, CO2 pipelines once.
    """
    design = design.copy()
    design["cost"] = design[["capex", "opex_fixed", "opex_variable"]].sum(axis=1)
    is_electricity_arc = (design["kind"] == "network") & (design["technology"] != "CO2_Pipeline")
    design.loc[is_electricity_arc, "cost"] /= 2
    design["group"] = [get_group(k, t) for k, t in zip(design["kind"], design["technology"])]
    costs = design.groupby(["case", "group"])["cost"].sum().unstack(fill_value=0)

    # Cross-check with the summary
    summary_cost = summary[["cost_capex_tecs", "cost_opex_tecs", "cost_capex_netws",
                            "cost_opex_netws"]].sum(axis=1)
    deviation = (costs.sum(axis=1) - summary_cost.reindex(costs.index)).abs().max()
    print(f"Largest deviation h5 design vs. summary: {deviation / 1e6:.3f} M EUR")
    return costs


def get_specific_differences(summary, values):
    """
    Difference to the No DAC run of the same climate year per tonne of negative emissions
    """
    runs = summary[["dac_configuration", "emission_target", "climate_year", "emissions_neg"]]
    values = runs.join(values, how="inner")
    columns = [column for column in values.columns if column not in runs.columns]
    no_dac = values[values["dac_configuration"] == "No DAC"].set_index("climate_year")
    targets = values[values["dac_configuration"] != "No DAC"].copy()
    for column in columns:
        targets[column] = ((targets[column] - targets["climate_year"].map(no_dac[column]))
                           / targets["emissions_neg"])
    targets["target_Mt"] = targets["emissions_neg"] / 1e6
    return targets.sort_values(["climate_year", "dac_configuration", "target_Mt"])


def get_electricity_demand(operation):
    """
    Electricity use of DAC and heat pumps per run (MWh/yr)
    """
    is_dac_supply = operation["technology"].str.startswith(("DAC_Adsorption", "HeatPump"))
    demand = operation[is_dac_supply & (operation["variable"] == "electricity_input")]
    return demand.groupby("case")["value"].sum().rename("dac_electricity_demand")


def save(fig, filename):
    fig.savefig(figure_dir / filename, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {figure_dir / filename}")


def plot_lines(targets, column, ylabel, filename, ylim=None):
    """
    One panel per climate year, one line per configuration over the target
    """
    climate_years = sorted(targets["climate_year"].unique())
    fig, axes = plt.subplots(1, len(climate_years), figsize=(9, 3.4), sharey=True)
    for ax, cy in zip(axes, climate_years):
        for configuration, (color, marker) in CONFIGURATIONS.items():
            runs = targets[(targets["climate_year"] == cy)
                           & (targets["dac_configuration"] == configuration)]
            ax.plot(runs["target_Mt"], runs[column], color=color, linewidth=2, marker=marker,
                    markersize=7, markeredgecolor="white", markeredgewidth=1, label=configuration)
        ax.set_title(f"cy {cy}", fontsize=10)
        ax.set_xlabel("Negative emissions (Mt/yr)")
        ax.set_xticks([2, 4, 6, 8])
    axes[0].set_ylabel(ylabel)
    if ylim:
        axes[0].set_ylim(*ylim)
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.tight_layout()
    save(fig, filename)


def plot_capture_cost(targets, filename):
    """
    Capture cost of all climate years in one chart: color and marker = configuration, line
    style = climate year. Hollow markers: cost per tonne of net reduction where it differs
    (positive emissions below the baseline), plotted at the net reduction.
    """
    line_styles = {1995: "-", 2008: "--", 2009: ":"}
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for configuration, (color, marker) in CONFIGURATIONS.items():
        for cy, line_style in line_styles.items():
            runs = targets[(targets["climate_year"] == cy)
                           & (targets["dac_configuration"] == configuration)]
            ax.plot(runs["target_Mt"], runs["total_npv"], color=color,
                    linestyle=line_style, linewidth=2, marker=marker, markersize=7,
                    markeredgecolor="white", markeredgewidth=1)
            differs = (runs["net_reduction_Mt"] - runs["target_Mt"]) > 0.01
            ax.scatter(runs.loc[differs, "net_reduction_Mt"], runs.loc[differs, "cost_per_net_reduction"],
                       facecolor="white", edgecolor=color, marker=marker, s=40, zorder=3)
    # Two legends: configuration (color/marker) and climate year (line style)
    configuration_handles = [plt.Line2D([], [], color=color, marker=marker, linewidth=2,
                                        markeredgecolor="white", label=configuration)
                             for configuration, (color, marker) in CONFIGURATIONS.items()]
    year_handles = [plt.Line2D([], [], color=GREY, linestyle=line_style, linewidth=2, label=f"cy {cy}")
                    for cy, line_style in line_styles.items()]
    hollow_handle = [plt.Line2D([], [], color=GREY, marker="o", linestyle="", markerfacecolor="white",
                                label="Per tonne of net\nreduction (if different)")]
    legend = ax.legend(handles=configuration_handles, loc="upper left",
                       bbox_to_anchor=(1.02, 1), frameon=False, title="Configuration")
    ax.add_artist(legend)
    ax.legend(handles=year_handles + hollow_handle, loc="upper left", bbox_to_anchor=(1.02, 0.55),
              frameon=False, title="Climate year")
    ax.set_xlabel("Negative emissions (Mt/yr)")
    ax.set_ylabel("Capture cost (EUR/t)")
    ax.set_xticks([2, 4, 6, 8])
    ax.set_ylim(950, 1180)
    fig.tight_layout()
    save(fig, filename)


def plot_cost_by_group(targets, filename):
    """
    Capture cost split by technology group (EUR/t), one panel per configuration
    """
    fig, axes = plt.subplots(1, len(CONFIGURATIONS), figsize=(12, 4), sharey=True)
    for ax, configuration in zip(axes, CONFIGURATIONS):
        runs = targets[targets["dac_configuration"] == configuration]
        x = np.arange(len(runs)) + np.repeat(np.arange(3) * 0.6, 4)[:len(runs)]
        bottom_pos = np.zeros(len(runs))
        bottom_neg = np.zeros(len(runs))
        for group, color in GROUP_COLORS.items():
            values = runs[group].to_numpy()
            bottom = np.where(values >= 0, bottom_pos, bottom_neg)
            ax.bar(x, values, 0.75, bottom=bottom, color=color, edgecolor="white", linewidth=0.8,
                   label=group)
            bottom_pos += np.clip(values, 0, None)
            bottom_neg += np.clip(values, None, 0)
        ax.scatter(x, runs["total_npv"], color="black", marker="D", s=16, zorder=3, label="Total")
        ax.axhline(0, color=GREY, linewidth=0.8)
        labels = [f"{target:.0f}" for target in runs["target_Mt"]]
        ax.set_xticks(x, labels, fontsize=8)
        for i, cy in enumerate(sorted(runs["climate_year"].unique())):
            ax.text(x[4 * i:4 * i + 4].mean(), -260, f"cy {cy}", ha="center", fontsize=9)
        ax.set_title(configuration, fontsize=10)
    axes[0].set_ylabel("Capture cost (EUR/t)")
    axes[0].set_ylim(-280, 1300)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=5, frameon=False,
               bbox_to_anchor=(0.5, 1.1), fontsize=8)
    fig.text(0.5, -0.02, "Negative emissions (Mt/yr) per climate year", ha="center", fontsize=9)
    fig.tight_layout()
    save(fig, filename)


summary = pd.read_csv(data_dir / "Summary_2040_processed.csv").set_index("case")
design = pd.read_csv(data_dir / "design_costs.csv")
operation = pd.read_csv(data_dir / "node_operation.csv")

costs = get_costs_by_group(summary, design)
costs = costs.join(summary[["total_npv", "cost_imports", "carbon_cost", "emissions_pos"]])
costs = costs.join(get_electricity_demand(operation)).fillna({"dac_electricity_demand": 0})
targets = get_specific_differences(summary, costs)
targets["Imports + carbon cost"] = targets["cost_imports"] + targets["carbon_cost"]
# Net reduction = negative emissions + reduction of positive emissions vs. No DAC
no_dac = summary[summary["dac_configuration"] == "No DAC"].set_index("climate_year")
emissions_pos_reduction = (targets["climate_year"].map(no_dac["emissions_pos"])
                           - summary.loc[targets.index, "emissions_pos"])
targets["net_reduction_Mt"] = targets["target_Mt"] + emissions_pos_reduction / 1e6
targets["cost_per_net_reduction"] = (targets["total_npv"] * targets["target_Mt"]
                                     / targets["net_reduction_Mt"])
targets["Electricity supply"] = targets[ELECTRICITY_GROUPS].sum(axis=1)
# Cost of the additional electricity supply per MWh used by DAC and heat pumps
targets["electricity_cost_per_MWh"] = (targets["Electricity supply"]
                                       / targets["dac_electricity_demand"])
targets.to_csv(data_dir / "capture_cost_by_group.csv")
print(f"Saved {data_dir / 'capture_cost_by_group.csv'}")

plot_capture_cost(targets, "fig1_capture_cost.png")
plot_cost_by_group(targets, "fig2_capture_cost_by_technology.png")
plot_lines(targets, "dac_electricity_demand", "Electricity, DAC + heat pumps (MWh/t)",
           "fig3_electricity_per_tonne.png", (0, 6))
plot_lines(targets, "electricity_cost_per_MWh", "Electricity supply cost (EUR/MWh)",
           "fig4_electricity_cost_per_MWh.png", (0, 80))
