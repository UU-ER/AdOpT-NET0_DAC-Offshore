from pathlib import Path
import pandas as pd
from read_data import read_results_from_h5

path_result_1 = Path(r"A:\ResearchData\MESNS\00_FinalResults\v01\2040_costs\2040_costs_Synergies_co2tax200_cy1995.h5")
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

# Capacities of all technologies per node
sizes_1 = tec_design_1[tec_design_1["Variable"] == "size"].set_index(["Node", "Technology"])["Value"]
sizes_2 = tec_design_2[tec_design_2["Variable"] == "size"].set_index(["Node", "Technology"])["Value"]
for node, tec in sorted(set(sizes_1.index) | set(sizes_2.index)):
    size_1 = sizes_1.get((node, tec), 0)
    size_2 = sizes_2.get((node, tec), 0)
    comparison.append(
        {"Variable": "Capacity", "Node": node, "Carrier": tec, "Result_1": size_1, "Result_2": size_2,
         "Delta": size_2 - size_1})

# Export to CSV
df_comparison = pd.DataFrame(comparison)
output_path = Path(__file__).parent / "results_comparison.csv"
df_comparison.to_csv(output_path, index=False)
