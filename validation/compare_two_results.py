from pathlib import Path
import pandas as pd
from read_data import read_results_from_h5

path_result_1 = Path(r"A:\ResearchData\MESNS\00_FinalResults\v01\2040_costs\2040_costs_Synergies_co2tax100_cy1995.h5")
path_result_2 = Path(r"C:\Users\jwiegner\OneDrive - ETH Zurich\00_Papers_Journal\00_2025-DACOffshore\DAC-Offshore-MaianJan\cy1995\no_dac_new\optimization_results.h5")

# Read results from both files
results_1 = read_results_from_h5(str(path_result_1))
results_2 = read_results_from_h5(str(path_result_2))

ebalance_1 = results_1["energybalance"]  # columns: (Period, Node, Carrier, Variable), rows: timesteps
ebalance_2 = results_2["energybalance"]
summary_1 = results_1["summary"]  # columns are 1-tuples, e.g. ("emissions_net",)
summary_2 = results_2["summary"]
tec_design_1 = results_1["technology_design"]  # columns: Period, Node, Technology, Variable, Value
tec_design_2 = results_2["technology_design"]
tec_operation_1 = results_1["technology_operation"]  # columns: (Period, Node, Technology, Variable), rows: timesteps
tec_operation_2 = results_2["technology_operation"]

comparison = []


def get_sum(ebalance, node, carrier, variable):
    try:
        return ebalance.xs((node, carrier, variable), level=("Node", "Carrier", "Variable"), axis=1).sum().sum()
    except KeyError:
        return 0


# Total annual electricity demand per node
for node in ebalance_1.columns.get_level_values("Node").unique():
    demand_1 = get_sum(ebalance_1, node, "electricity", "demand")
    demand_2 = get_sum(ebalance_2, node, "electricity", "demand")
    comparison.append({"Variable": "Demand", "Node": node, "Carrier": "electricity", "Result_1": demand_1, "Result_2": demand_2, "Delta": demand_2 - demand_1})

# Total generic_production per node
for node in ebalance_1.columns.get_level_values("Node").unique():
    value_1 = get_sum(ebalance_1, node, "electricity", "generic_production")
    value_2 = get_sum(ebalance_2, node, "electricity", "generic_production")
    comparison.append({"Variable": "Generic Production", "Node": node, "Carrier": "electricity", "Result_1": value_1, "Result_2": value_2, "Delta": value_2 - value_1})

# Imports per carrier per node
for carrier in ebalance_1.columns.get_level_values("Carrier").unique():
    for node in ebalance_1.columns.get_level_values("Node").unique():
        import_1 = get_sum(ebalance_1, node, carrier, "import")
        import_2 = get_sum(ebalance_2, node, carrier, "import")
        comparison.append(
            {"Variable": "Imports", "Node": node, "Carrier": carrier, "Result_1": import_1, "Result_2": import_2, "Delta": import_2 - import_1})

# Total emissions
total_emissions_1 = summary_1[("emissions_net",)].values[0]
total_emissions_2 = summary_2[("emissions_net",)].values[0]
comparison.append(
    {"Variable": "Total_Emissions", "Node": None, "Carrier": None, "Result_1": total_emissions_1, "Result_2": total_emissions_2,
     "Delta": total_emissions_2 - total_emissions_1})

# Capacity, CAPEX, OPEX (fixed/variable) and CO2 cost of all technologies per node
pivot_1 = tec_design_1.pivot_table(index=["Node", "Technology"], columns="Variable", values="Value", aggfunc="sum")
pivot_2 = tec_design_2.pivot_table(index=["Node", "Technology"], columns="Variable", values="Value", aggfunc="sum")

# Effective carbon price (EUR/tCO2) derived from total carbon cost / total net emissions, used to split CO2 cost per technology
carbon_price_1 = summary_1[("carbon_cost",)].values[0] / summary_1[("emissions_net",)].values[0] if summary_1[("emissions_net",)].values[0] else 0
carbon_price_2 = summary_2[("carbon_cost",)].values[0] / summary_2[("emissions_net",)].values[0] if summary_2[("emissions_net",)].values[0] else 0

tec_metrics = {"Capacity": "size", "CAPEX": "capex_tot", "OPEX_Fixed": "opex_fixed", "OPEX_Variable": "opex_variable"}

for node, tec in sorted(set(pivot_1.index) | set(pivot_2.index)):
    row_1 = pivot_1.loc[(node, tec)] if (node, tec) in pivot_1.index else pd.Series(dtype=float)
    row_2 = pivot_2.loc[(node, tec)] if (node, tec) in pivot_2.index else pd.Series(dtype=float)

    for label, col in tec_metrics.items():
        val_1 = row_1.get(col, 0)
        val_2 = row_2.get(col, 0)
        comparison.append(
            {"Variable": label, "Node": node, "Carrier": tec, "Result_1": val_1, "Result_2": val_2,
             "Delta": val_2 - val_1})

    net_emissions_1 = row_1.get("emissions_pos", 0) - row_1.get("emissions_neg", 0)
    net_emissions_2 = row_2.get("emissions_pos", 0) - row_2.get("emissions_neg", 0)
    co2_cost_1 = net_emissions_1 * carbon_price_1
    co2_cost_2 = net_emissions_2 * carbon_price_2
    comparison.append(
        {"Variable": "CO2_Cost", "Node": node, "Carrier": tec, "Result_1": co2_cost_1, "Result_2": co2_cost_2,
         "Delta": co2_cost_2 - co2_cost_1})


# Total in/outputs of all technologies (summed over time) per node
in_out_vars = [v for v in tec_operation_1.columns.get_level_values("Variable").unique()
               if v.endswith("_input") or v.endswith("_output")]
totals_1 = tec_operation_1.sum().droplevel("Period")
totals_2 = tec_operation_2.sum().droplevel("Period")
for node, tec, variable in sorted(set(
        idx for idx in totals_1.index if idx[2] in in_out_vars
) | set(
        idx for idx in totals_2.index if idx[2] in in_out_vars
)):
    value_1 = totals_1.get((node, tec, variable), 0)
    value_2 = totals_2.get((node, tec, variable), 0)
    comparison.append(
        {"Variable": variable, "Node": node, "Carrier": tec, "Result_1": value_1, "Result_2": value_2,
         "Delta": value_2 - value_1})

# Export to CSV
df_comparison = pd.DataFrame(comparison)
output_path = Path(__file__).parent / "results_comparison.csv"
df_comparison.to_csv(output_path, index=False)
