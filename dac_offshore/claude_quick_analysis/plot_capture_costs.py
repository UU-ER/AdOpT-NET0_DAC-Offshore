"""
Specific capture costs of the emission target runs. Run concat_summaries.py and
extract_run_metrics.py first.
- Average and marginal capture costs from the processed summary
- Capture cost by technology and DAC operation from the h5 data (technology and network design)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

here = Path(__file__).parent
data_dir = here / "data"
figure_dir = here / "figures"
figure_dir.mkdir(exist_ok=True)

COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
GREY = "#52514e"
DAC_CONFIGURATIONS = {"DAC": COLORS[0], "DAC onshore": COLORS[1], "DAC offshore": COLORS[2]}
COST_COMPONENTS = {
    "cost_capex_tecs": "CAPEX technologies",
    "cost_opex_tecs": "OPEX technologies",
    "cost_capex_netws": "CAPEX networks",
    "cost_opex_netws": "OPEX networks",
    "cost_imports": "Imports",
    "carbon_cost": "Carbon cost",
}

# Summary of an earlier download, contains runs that are not in the current results folder (cy 2008)
FIRST_GLANCE_SUMMARY = data_dir / "Summary_2040_processed_first_glance.csv"

# Technology prefix -> group for the cost breakdown
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

# Annualised DAC cost from the technology data (DAC_Adsorption_*.json)
DAC_UNIT_CAPEX = 5672.63  # EUR per t/yr
DAC_OPEX_FIXED = 0.346  # share of annualised CAPEX
DISCOUNT_RATE = 0.1
LIFETIME = 25
DAC_PRODUCTIVITY = 1.054  # captured / installed size, from the max runs

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": "#e5e5e5",
    "axes.axisbelow": True,
})


def annualised_dac_cost_per_tonne():
    annuity_factor = DISCOUNT_RATE / (1 - (1 + DISCOUNT_RATE) ** -LIFETIME)
    annualised_capex = DAC_UNIT_CAPEX * annuity_factor
    return annualised_capex * (1 + DAC_OPEX_FIXED) / DAC_PRODUCTIVITY


def add_cost_differences(summary):
    """
    Adds the cost difference to the No DAC run of the same climate year per tonne captured
    and the marginal cost between two consecutive targets
    """
    no_dac = summary[summary["dac_configuration"] == "No DAC"].set_index("climate_year")
    for column in COST_COMPONENTS:
        additional_cost = summary[column] - summary["climate_year"].map(no_dac[column])
        summary[f"specific_{column}"] = additional_cost / summary["emissions_neg"]

    summary = summary.sort_values(["dac_configuration", "climate_year", "emissions_neg"])
    groups = summary.groupby(["dac_configuration", "climate_year"])
    summary["marginal_capture_cost"] = (groups["total_npv"].diff()
                                        / groups["emissions_neg"].diff())
    return summary


def get_technology_group(technology):
    for prefix, group in TECHNOLOGY_GROUPS.items():
        if technology.startswith(prefix):
            return group
    return "Other"


def get_capture_cost_by_technology(summary, design, network_design):
    """
    Annualised cost (CAPEX + fixed and variable OPEX) per technology group and network,
    as difference to the No DAC run of the same climate year per tonne captured (EUR/t)
    """
    design = design[design["Variable"].isin(["capex_tot", "opex_fixed", "opex_variable"])].copy()
    design["group"] = design["Technology"].apply(get_technology_group)
    costs = design.groupby(["case", "group"])["Value"].sum().unstack(fill_value=0)

    # Every arc is saved in both directions, so the network costs are counted twice
    network_design = network_design.copy()
    network_design["group"] = np.where(network_design["Network"] == "CO2_Pipeline",
                                       "CO2 transport & storage", "Electricity networks")
    network_design["cost"] = network_design[["capex", "opex_fixed", "opex_variable"]].sum(axis=1) / 2
    network_costs = network_design.groupby(["case", "group"])["cost"].sum().unstack(fill_value=0)
    costs = costs.add(network_costs, fill_value=0)

    runs = summary.set_index("case")[["dac_configuration", "emission_target", "climate_year",
                                      "emissions_neg", "specific_capture_cost"]]
    costs = runs.join(costs, how="inner")
    groups = [column for column in costs.columns if column not in runs.columns]

    no_dac = costs[costs["dac_configuration"] == "No DAC"].set_index("climate_year")
    for group in groups:
        additional_cost = costs[group] - costs["climate_year"].map(no_dac[group])
        costs[group] = additional_cost / costs["emissions_neg"]
    return costs[costs["emission_target"].str.endswith("%")].reset_index()


def get_dac_operation(summary, design, metrics):
    """
    DAC capacity (t/yr), utilisation, energy use per tonne (MWh/t) and sites per run
    """
    dac = design[design["Technology"].str.startswith("DAC") & (design["Variable"] == "size")]
    dac = dac[dac["Value"] > 1]
    onshore = dac[dac["Technology"].str.endswith("onshore")]
    offshore = dac[dac["Technology"].str.endswith("offshore")]
    metrics = metrics.set_index("case")
    captured = metrics["dac_captured_onshore"] + metrics["dac_captured_offshore"]

    operation = pd.DataFrame({
        "dac_size_onshore": onshore.groupby("case")["Value"].sum(),
        "dac_size_offshore": offshore.groupby("case")["Value"].sum(),
        "dac_captured": captured,
        "dac_electricity_per_t": metrics["dac_electricity"] / captured,
        "dac_heat_per_t": metrics["dac_heat"] / captured,
        "dac_sites_onshore": onshore.groupby("case")["Node"].apply(lambda nodes: ", ".join(sorted(nodes))),
        "dac_sites_offshore": offshore.groupby("case")["Node"].apply(lambda nodes: ", ".join(sorted(nodes))),
    })
    operation[["dac_size_onshore", "dac_size_offshore"]] = operation[
        ["dac_size_onshore", "dac_size_offshore"]].fillna(0)
    dac_size = operation["dac_size_onshore"] + operation["dac_size_offshore"]
    operation["dac_utilisation"] = operation["dac_captured"] / dac_size

    runs = summary.set_index("case")[["dac_configuration", "emission_target", "climate_year"]]
    operation = runs.join(operation, how="inner")
    return operation[operation["emission_target"].str.endswith("%")].reset_index()


def save(fig, filename):
    fig.savefig(figure_dir / filename, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {figure_dir / filename}")


def plot_specific_capture_cost(targets):
    """
    Average capture cost (vs. No DAC) over negative emissions, one panel per climate year
    """
    climate_years = sorted(targets["climate_year"].unique())
    fig, axes = plt.subplots(1, len(climate_years), figsize=(9, 3.4), sharey=True)
    for ax, cy in zip(axes, climate_years):
        for dac_configuration, color in DAC_CONFIGURATIONS.items():
            runs = targets[(targets["climate_year"] == cy)
                           & (targets["dac_configuration"] == dac_configuration)]
            ax.plot(runs["emissions_neg"] / 1e6, runs["specific_capture_cost"], color=color,
                    linewidth=2, marker="o", markersize=7, label=dac_configuration)
        ax.axhline(annualised_dac_cost_per_tonne(), color=GREY, linewidth=0.8, linestyle="--")
        ax.set_title(f"cy {cy}", fontsize=10)
        ax.set_xlabel("Negative emissions (Mt/yr)")
        ax.set_xlim(2, 17)
    axes[0].set_ylabel("Capture cost (EUR/t)")
    axes[0].set_ylim(0, 1400)
    axes[0].text(2.3, annualised_dac_cost_per_tonne() - 25, "DAC unit alone (CAPEX + fixed OPEX)",
                 fontsize=7, color=GREY, va="top")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.tight_layout()
    save(fig, "fig5_specific_capture_cost.png")


def plot_capture_cost_by_technology(costs):
    """
    Capture cost split by technology group (EUR/t), one panel per DAC configuration.
    Power plants and hydro (< 5 EUR/t) are only included in the total.
    """
    run_counts = [len(costs[costs["dac_configuration"] == d]) for d in DAC_CONFIGURATIONS]
    fig, axes = plt.subplots(1, len(DAC_CONFIGURATIONS), figsize=(11, 3.8), sharey=True,
                             gridspec_kw={"width_ratios": run_counts})

    for ax, dac_configuration in zip(axes, DAC_CONFIGURATIONS):
        runs = costs[costs["dac_configuration"] == dac_configuration]
        runs = runs.sort_values(["climate_year", "emissions_neg"])
        x = np.arange(len(runs))
        bottom_pos = np.zeros(len(runs))
        bottom_neg = np.zeros(len(runs))
        for group, color in GROUP_COLORS.items():
            values = runs[group].to_numpy()
            bottom = np.where(values >= 0, bottom_pos, bottom_neg)
            ax.bar(x, values, 0.7, bottom=bottom, color=color, edgecolor="white", linewidth=0.5,
                   label=group)
            bottom_pos += np.clip(values, 0, None)
            bottom_neg += np.clip(values, None, 0)
        ax.scatter(x, runs["specific_capture_cost"], color="black", marker="D", s=16, zorder=3,
                   label="Total")
        ax.axhline(0, color=GREY, linewidth=0.8)
        labels = [f"{cy}\n{target}" for cy, target in zip(runs["climate_year"], runs["emission_target"])]
        ax.set_xticks(x, labels, fontsize=8)
        ax.set_title(dac_configuration, fontsize=10)

    axes[0].set_ylabel("Capture cost (EUR/t)")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=5, frameon=False,
               bbox_to_anchor=(0.5, 1.12), fontsize=8)
    fig.tight_layout()
    save(fig, "fig6_capture_cost_by_technology.png")


summary = pd.read_csv(data_dir / "Summary_2040_processed.csv")

# Add runs from the first download that are not in the current results folder
first_glance = pd.read_csv(FIRST_GLANCE_SUMMARY)
first_glance = first_glance[~first_glance["case"].isin(summary["case"])]
summary_all = add_cost_differences(pd.concat([summary, first_glance], ignore_index=True))

targets = summary_all[summary_all["emission_target"].str.endswith("%")]
targets.to_csv(data_dir / "capture_costs.csv", index=False)
print(f"Saved {data_dir / 'capture_costs.csv'}")
print(f"Annualised DAC cost: {annualised_dac_cost_per_tonne():.0f} EUR/t")

design = pd.read_csv(data_dir / "technology_design.csv")
network_design = pd.read_csv(data_dir / "network_design.csv")
metrics = pd.read_csv(data_dir / "run_metrics.csv")

costs_by_technology = get_capture_cost_by_technology(summary, design, network_design)
costs_by_technology.to_csv(data_dir / "capture_cost_by_technology.csv", index=False)
print(f"Saved {data_dir / 'capture_cost_by_technology.csv'}")

dac_operation = get_dac_operation(summary, design, metrics)
dac_operation.to_csv(data_dir / "dac_operation.csv", index=False)
print(f"Saved {data_dir / 'dac_operation.csv'}")

plot_specific_capture_cost(targets)
plot_capture_cost_by_technology(costs_by_technology)
