"""
Plots the 2040 max negative emission results against the No DAC baseline.
Run concat_summaries.py and extract_run_metrics.py first.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

here = Path(__file__).parent
data_dir = here / "data"
figure_dir = here / "figures"
figure_dir.mkdir(exist_ok=True)

summary = pd.read_csv(data_dir / "Summary_2040_processed.csv")
metrics = pd.read_csv(data_dir / "run_metrics.csv")
design = pd.read_csv(data_dir / "technology_design.csv")

CLIMATE_YEARS = sorted(summary["climate_year"].unique())
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
GREY = "#52514e"

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": "#e5e5e5",
    "axes.axisbelow": True,
})


def get_run(df, dac_configuration, climate_year):
    selection = (df["dac_configuration"] == dac_configuration) & (df["climate_year"] == climate_year)
    return df[selection].iloc[0]


def save(fig, filename):
    fig.tight_layout()
    fig.savefig(figure_dir / filename, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {figure_dir / filename}")


def plot_emissions():
    """
    Positive, negative and net emissions per climate year (Mt/yr)
    """
    fig, ax = plt.subplots(figsize=(7, 3.8))
    x = np.arange(len(CLIMATE_YEARS))
    width = 0.38

    for i, (dac_configuration, label) in enumerate([("No DAC", "No DAC (cost min.)"),
                                                    ("DAC", "DAC (max. neg. emissions)")]):
        runs = [get_run(summary, dac_configuration, cy) for cy in CLIMATE_YEARS]
        pos = np.array([run["emissions_pos"] for run in runs]) / 1e6
        neg = np.array([run["emissions_neg"] for run in runs]) / 1e6
        net = np.array([run["emissions_net"] for run in runs]) / 1e6
        offset = (i - 0.5) * width

        ax.bar(x + offset, pos, width, color=COLORS[1], edgecolor="white", linewidth=1,
               label="Positive emissions" if i == 0 else None)
        ax.bar(x + offset, -neg, width, color=COLORS[0], edgecolor="white", linewidth=1,
               label="Negative emissions (DAC)" if i == 1 else None)
        ax.scatter(x + offset, net, color="black", marker="D", s=30, zorder=3,
                   label="Net emissions" if i == 0 else None)
        for xi, value in zip(x + offset, net):
            ax.annotate(f"{value:.1f}", (xi, value), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=8, color=GREY)
        for xi in x + offset:
            ax.text(xi, -88, label.split(" (")[0], ha="center", va="top", fontsize=8, color=GREY)

    ax.axhline(0, color=GREY, linewidth=0.8)
    ax.set_xticks(x, [f"cy {cy}" for cy in CLIMATE_YEARS])
    ax.tick_params(axis="x", pad=16)
    ax.set_ylabel("Emissions (Mt CO$_2$/yr)")
    ax.set_ylim(-95, 50)
    ax.legend(loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.12))
    save(fig, "fig1_emissions.png")


def plot_costs():
    """
    Cost breakdown, two panels since the max case is ~150x more expensive
    """
    components = {
        "cost_capex_tecs": "CAPEX technologies",
        "cost_opex_tecs": "OPEX technologies",
        "cost_capex_netws": "CAPEX networks",
        "cost_opex_netws": "OPEX networks",
        "cost_imports": "Imports",
        "carbon_cost": "Carbon cost",
    }
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6))
    panels = [("No DAC", "No DAC (cost min.)", 1e9, "bn EUR/yr"),
              ("DAC", "DAC (max. neg. emissions)", 1e12, "tn EUR/yr")]

    for ax, (dac_configuration, title, scale, unit) in zip(axes, panels):
        runs = [get_run(summary, dac_configuration, cy) for cy in CLIMATE_YEARS]
        bottom = np.zeros(len(runs))
        for color, (column, label) in zip(COLORS, components.items()):
            values = np.array([run[column] for run in runs]) / scale
            ax.bar([str(cy) for cy in CLIMATE_YEARS], values, 0.6, bottom=bottom,
                   color=color, edgecolor="white", linewidth=1, label=label)
            bottom += values
        for i, total in enumerate(bottom):
            ax.text(i, total, f"{total:.1f}", ha="center", va="bottom", fontsize=8, color=GREY)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(f"Total cost ({unit})")
        ax.set_xlabel("Climate year")

    axes[1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    save(fig, "fig2_costs.png")


def plot_dac_capacity():
    """
    Installed DAC capacity (t/yr) vs CO2 captured, per DAC type
    """
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    dac_sizes = design[(design["Variable"] == "size") & design["Technology"].str.startswith("DAC")]
    dac_sizes = dac_sizes.merge(summary[["case", "climate_year"]], on="case")

    x = np.arange(len(CLIMATE_YEARS))
    width = 0.2
    for i, location in enumerate(["onshore", "offshore"]):
        capacity = [dac_sizes[(dac_sizes["Technology"] == f"DAC_Adsorption_{location}")
                              & (dac_sizes["climate_year"] == cy)]["Value"].sum() / 1e6
                    for cy in CLIMATE_YEARS]
        captured = [get_run(metrics, "DAC", cy)[f"dac_captured_{location}"] / 1e6
                    for cy in CLIMATE_YEARS]
        offset = (2 * i - 1.5) * width
        ax.bar(x + offset, capacity, width, color=COLORS[2 * i], alpha=0.45, edgecolor="white",
               label=f"{location.capitalize()}: installed (= size_max)")
        ax.bar(x + offset + width, captured, width, color=COLORS[2 * i], edgecolor="white",
               label=f"{location.capitalize()}: captured")
        for xi, cap, cap_out in zip(x + offset + width, capacity, captured):
            ax.text(xi, cap_out, f"{cap_out / cap:.1%}", ha="center", va="bottom", fontsize=7,
                    color=GREY)

    ax.set_xticks(x, [f"cy {cy}" for cy in CLIMATE_YEARS])
    ax.set_ylabel("Mt CO$_2$/yr")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    save(fig, "fig3_dac_capacity.png")


def plot_upper_bound_utilisation():
    """
    Utilisation of the constraints that could limit the negative emissions (%).
    100% means the constraint is binding.
    """
    candidates = {
        "util_dac_min_hour": "DAC potential\n(output / max. output,\nlowest hour)",
        "util_co2_injection_rate": "CO$_2$ storage\n(injection rate)",
        "util_co2_storage_volume": "CO$_2$ storage\n(reservoir volume)",
        "util_vre_hours_without_curtailment": "VRE potential\n(hours without\ncurtailment)",
    }
    fig, ax = plt.subplots(figsize=(8, 3.4))
    x = np.arange(len(candidates))
    width = 0.25
    for i, cy in enumerate(CLIMATE_YEARS):
        run = get_run(metrics, "DAC", cy)
        values = [run[column] * 100 for column in candidates]
        ax.bar(x + (i - 1) * width, values, width, color=COLORS[i], edgecolor="white",
               label=f"cy {cy}")
        for xi, value in zip(x + (i - 1) * width, values):
            ax.text(xi, value, f"{value:.0f}", ha="center", va="bottom", fontsize=7, color=GREY)

    ax.axhline(100, color=GREY, linewidth=0.8, linestyle="--")
    ax.set_xticks(x, candidates.values(), fontsize=8)
    ax.set_ylabel("Utilisation (%)")
    ax.set_ylim(0, 115)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    save(fig, "fig4_upper_bound_utilisation.png")


plot_emissions()
plot_costs()
plot_dac_capacity()
plot_upper_bound_utilisation()
