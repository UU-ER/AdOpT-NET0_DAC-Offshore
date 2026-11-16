"""
Compares the offshore wind cost assumption of the model with the DEA source data and computes
the levelised cost of electricity (LCOE) of offshore wind, onshore wind and PV with the model inputs.
"""
from pathlib import Path

import pandas as pd

here = Path(__file__).parent
clean_data_path = here.parent / "clean_data"
TECHNOLOGY_COST_FILE = clean_data_path / "technologies_cost" / "TechnologyCost.xlsx"
NETWORK_COST_FILE = clean_data_path / "networks_cost" / "NetworkCost.xlsx"
OUTPUT_FILE = here / "data" / "offshore_wind_cost_check.csv"

YEAR = 2040
DISCOUNT_RATE = 0.1
PPI_FACTOR = 1.325399  # 2020 -> 2025, used in TechnologyCost.xlsx and NetworkCost.xlsx
DISTANCE_TO_SHORE = 175  # km, DEA reference far shore wind farm

# Mean capacity factors of the new VRE nodes in the model (max runs, cy 1995 and 2009)
CAPACITY_FACTORS = {"Offshore_Wind": 0.565, "Onshore_Wind": 0.34, "PV": 0.095}

# DEA 'Far shore Wind - DC connected - Fixed bottom', 2040 (MEUR2020/MW), sheet in TechnologyCost.xlsx
DEA_OFFSHORE_2040 = {
    "project development": 0.16,
    "turbines": 0.81,
    "foundation": 0.39,
    "array cables": 0.04,
    "substation": 0.97,
    "export cables": 0.53,
}


def annuity_factor(lifetime):
    return DISCOUNT_RATE / (1 - (1 + DISCOUNT_RATE) ** -lifetime)


def get_model_technology_costs():
    costs = pd.read_excel(TECHNOLOGY_COST_FILE, sheet_name="ToModel_2025", skiprows=1)
    costs = costs[(costs["Year"] == YEAR) & costs["Technology"].isin(CAPACITY_FACTORS.keys())]
    return costs.set_index("Technology")


def get_dc_offshore_link_cost():
    """
    Investment cost of a new DC offshore link per MW (EUR/MW): converter pair + cable to shore
    """
    costs = pd.read_excel(NETWORK_COST_FILE, sheet_name="ToModel_2025", header=1)
    dc_offshore = costs.set_index("Network").loc["electricityDC_offshore"]
    return dc_offshore["gamma2"] + dc_offshore["gamma4"] * DISTANCE_TO_SHORE, dc_offshore


def get_lcoe(unit_capex, opex_fixed, opex_variable, lifetime, capacity_factor):
    """
    LCOE (EUR/MWh). opex_fixed is given as share of the annualised CAPEX, as in the model
    """
    annualised_capex = unit_capex * annuity_factor(lifetime)
    annual_cost = annualised_capex * (1 + opex_fixed)
    return annual_cost / (capacity_factor * 8760) + opex_variable


technology_costs = get_model_technology_costs()
link_capex, dc_offshore = get_dc_offshore_link_cost()
link_lifetime = dc_offshore["Lifetime"]
link_cost_per_mwh = (link_capex * annuity_factor(link_lifetime) * (1 + dc_offshore["OPEX Fixed"])
                     / (CAPACITY_FACTORS["Offshore_Wind"] * 8760))

# CAPEX comparison for a far shore offshore wind farm incl. connection to shore (MEUR2025/MW)
dea_total = sum(DEA_OFFSHORE_2040.values()) * PPI_FACTOR
dea_without_grid = (sum(DEA_OFFSHORE_2040.values()) - DEA_OFFSHORE_2040["substation"]
                    - DEA_OFFSHORE_2040["export cables"]) * PPI_FACTOR
model_wind = technology_costs.loc["Offshore_Wind", "Investment Cost"] / 1e6
model_with_link = model_wind + link_capex / 1e6

capex_comparison = pd.DataFrame({
    "MEUR2025_per_MW": {
        "DEA 2040 total (turbine, foundation, substation, export cable)": dea_total,
        "DEA 2040 without substation and export cable": dea_without_grid,
        "Model Offshore_Wind (DEA total - export cables)": model_wind,
        f"Model DC offshore link ({DISTANCE_TO_SHORE} km, converter pair + cable)": link_capex / 1e6,
        "Model Offshore_Wind + DC link": model_with_link,
        "Consistent: DEA without substation/export cable + DC link": dea_without_grid + link_capex / 1e6,
    }
})
print(capex_comparison.round(2).to_string())

# LCOE with the model inputs
lcoe = {}
for technology, row in technology_costs.iterrows():
    lcoe[technology] = get_lcoe(row["Investment Cost"], row["OPEX Fixed"], row["OPEX Variable"],
                                row["Lifetime"], CAPACITY_FACTORS[technology])
offshore = technology_costs.loc["Offshore_Wind"]
lcoe["Offshore_Wind + DC link"] = lcoe["Offshore_Wind"] + link_cost_per_mwh
lcoe["Offshore_Wind without substation"] = get_lcoe(
    dea_without_grid * 1e6, offshore["OPEX Fixed"], offshore["OPEX Variable"],
    offshore["Lifetime"], CAPACITY_FACTORS["Offshore_Wind"])
lcoe["Offshore_Wind without substation + DC link"] = (lcoe["Offshore_Wind without substation"]
                                                     + link_cost_per_mwh)
lcoe = pd.Series(lcoe, name="LCOE_EUR_per_MWh")
print(lcoe.round(1).to_string())

OUTPUT_FILE.parent.mkdir(exist_ok=True)
pd.concat([capex_comparison["MEUR2025_per_MW"], lcoe]).to_csv(OUTPUT_FILE, header=["value"])
print(f"Saved {OUTPUT_FILE}")
