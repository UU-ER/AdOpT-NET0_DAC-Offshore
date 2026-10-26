from pathlib import Path
import pandas as pd
import re
from read_data import read_technology_design

result_folder = Path(r"H:\ResearchData\MESNS\00_FinalResults\v01\2040_costs")
max_vre_potential_path = Path(r"C:\Users\jwiegner\PycharmProjects\AdOpT_DAC-Offshore\dac_offshore\clean_data\max_re_cap\max_re_nodes.csv")
violation_path = Path(r"C:\Users\jwiegner\PycharmProjects\AdOpT_DAC-Offshore\validate_vre_potential\offshore_wind_violations.csv")

# Load max offshore wind potential
max_potential = pd.read_csv(max_vre_potential_path)
max_potential = max_potential[["Node", "RemainingPotential_Wind_off"]].set_index("Node")

# Check each H5 file
results = []

for h5_file in sorted(result_folder.glob("*.h5")):
    # Extract climate year and scenario from filename
    # Convention: 2040_costs_<scenario>_co2tax<value>_cy<year>.h5
    filename = h5_file.stem  # filename without extension
    
    # Extract scenario: between "2040_costs_" and "_co2tax"
    scenario_match = re.search(r'2040_costs_(.+)_co2tax', filename)
    scenario = scenario_match.group(1) if scenario_match else "Unknown"
    
    # Extract climate year: after "cy"
    year_match = re.search(r'cy(\d+)', filename)
    climate_year = year_match.group(1) if year_match else "Unknown"
    
    tech_design = read_technology_design(str(h5_file))
    offshore_wind = tech_design[tech_design["Technology"] == "Offshore_Wind"]
    
    if offshore_wind.empty:
        continue
    
    # Get max installed capacity per node
    node_capacities = offshore_wind[offshore_wind["Variable"] == "size"]
    
    for index, row in node_capacities.iterrows():
        node = row["Node"]
        capacity = row["Value"]
        max_cap = max_potential.loc[node, "RemainingPotential_Wind_off"]
        delta = capacity - max_cap
        
        # Only include rows where capacity exceeds potential
        if capacity > max_cap:
            results.append({
                "Climate_Year": climate_year,
                "Scenario": scenario,
                "H5_File": h5_file.name,
                "Node": node,
                "Max_Potential_MW": max_cap,
                "Actual_Capacity_MW": capacity,
                "Delta_MW": delta
            })

# Export to CSV
if results:
    df_results = pd.DataFrame(results)
    df_results.to_csv(violation_path, index=False)

