import pandas as pd
import h5py
from mes_north_sea.postprocessing.utilities import extract_datasets_from_h5_group

def get_tec_production(path):
    with h5py.File(path + '/optimization_results.h5', 'r') as hdf_file:
        return extract_datasets_from_h5_group(hdf_file["operation/technology_operation"])

def get_annual_tec_production(path):
    tec_operation_dict = get_tec_production(path)
    return pd.DataFrame(tec_operation_dict).sum().groupby(level=[2, 3]).sum()

def get_storage_capacity(path):
    tec_operation = pd.DataFrame(get_tec_production(path))
    tec_operation_storage = tec_operation.loc[:, ((tec_operation.columns.get_level_values(2).str.startswith(
        "Storage_Battery")) & (tec_operation.columns.get_level_values(3) == "storage_level"))]
    cap = 0
    for col in tec_operation_storage:
        cap = cap + (tec_operation_storage[col].max() - tec_operation_storage[col].min())

    return cap


results_all = pd.read_excel(
        "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/Summary_processed.xlsx",
        header=[0, 1, 2], index_col=0)

# 2030 curtailment in storage scenarios
# 2030 storage capacities in storage scenarios
cys = [1995, 2008, 2009]

path_storage_all = {}
path_storage_all[1995] = r"\\Soliscom.uu.nl\geo\USERS\StaffUsers\6574114\EhubResults\MES NorthSea\20250515\2030\emission_reduction\20250521043736_Battery_all_minCost_at_0.9-1"
path_storage_all[2008] = r"\\Soliscom.uu.nl\geo\USERS\StaffUsers\6574114\EhubResults\MES NorthSea\20250515\2030\emission_reduction\20250521084035_Battery_all_minCost_at_0.9-1"
path_storage_all[2009] = r"\\Soliscom.uu.nl\geo\USERS\StaffUsers\6574114\EhubResults\MES NorthSea\20250515\2030\emission_reduction\20250521061914_Battery_all_minCost_at_0.9-1"
path_storage_offshore = {}
path_storage_offshore[1995] = r"\\Soliscom.uu.nl\geo\USERS\StaffUsers\6574114\EhubResults\MES NorthSea\20250515\2030\emission_reduction\20250520223741_Battery_off_minCost_at_0.9-1"
path_storage_offshore[2008] = r"\\Soliscom.uu.nl\geo\USERS\StaffUsers\6574114\EhubResults\MES NorthSea\20250515\2030\emission_reduction\20250521004203_Battery_off_minCost_at_0.9-1"
path_storage_offshore[2009] = r"\\Soliscom.uu.nl\geo\USERS\StaffUsers\6574114\EhubResults\MES NorthSea\20250515\2030\emission_reduction\20250520234309_Battery_off_minCost_at_0.9-1"
for cy in cys:
    print(f"{cy}")

    curtailment = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline") & (results_all[("global", "global", "Subcase")] == "Baseline")][
        ("global", "electricity", "curtailment")].values[0]
    generic_production = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline") & (results_all[("global", "global", "Subcase")] == "Baseline")][
        ("global", "electricity", "generic_production")].values[0]
    print(f"Curtailed electricity in Baseline = {round((curtailment)/1000000, 3)}")
    print(f"Curtailed fraction of electricity in Baseline = {round((curtailment)/(generic_production + curtailment), 3)}")

    curtailment = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Storage") & (results_all[("global", "global", "Subcase")] == "all")  & (results_all[("global", "global", "objective")] == "min emissions")][
        ("global", "electricity", "curtailment")].values[0]
    generic_production = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Storage") & (results_all[("global", "global", "Subcase")] == "all")  & (results_all[("global", "global", "objective")] == "min emissions")][
        ("global", "electricity", "generic_production")].values[0]
    print(f"Curtailed electricity in Storage All = {round((curtailment)/1000000, 3)}")
    print(f"Curtailed fraction of electricity in Storage All = {round((curtailment)/(generic_production + curtailment), 3)}")

    cap = get_storage_capacity(path_storage_all[cy])
    print(f"Storage all | Required storage capacity is {cap/1000} GWh")
    cap = get_storage_capacity(path_storage_offshore[cy])
    print(f"Storage offshore only | Required storage capacity is {cap/1000} GWh")




# 2030 Synergies scenario
for cy in cys:
    print(f"{cy}")

    results_cy = results_all[(results_all[("global", "global", "cy")] == cy)]
    capacities_raw = results_cy.loc[:, ["tec_sizes"]]

    #cf of nuclear for baseline
    path_baseline = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline")][
        ("global", "global", "Path")].values[0]
    path_synergies = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "All")][
        ("global", "global", "Path")].values[0]

    annual_production_baseline = get_annual_tec_production(path_baseline)
    annual_production_synergies = get_annual_tec_production(path_synergies)

    # Nuclear capacity
    c_nuclear = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline")][
        ("tec_sizes", "PowerPlant_Nuclear_existing", "size")].values[0]
    # Nuclear production baseline
    cf_baseline = annual_production_baseline["PowerPlant_Nuclear_existing"]["electricity_output"] / (c_nuclear*8760)
    # Nuclear production synergies
    cf_synergies = annual_production_synergies["PowerPlant_Nuclear_existing"]["electricity_output"] / (c_nuclear*8760)

    print(f"CF_nuclear (Baseline) = {round(cf_baseline,2)}")
    print(f"CF_nuclear (Synergies) = {round(cf_synergies,2)}")

    #export of H2
    # export_h2 = results_all[
    #     (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "All")][
    #     ("global", "hydrogen", "export")].values[0]
    production_h2 = (annual_production_synergies["Electrolyser_PEM_offshore"]["hydrogen_output"] + annual_production_synergies["Electrolyser_PEM"]["hydrogen_output"]) / 1000
    input_h2_gt = annual_production_synergies["PowerPlant_Gas_existing"]["hydrogen_input"] / 1000
    input_h2_storage = annual_production_synergies["Storage_Hydrogen"]["hydrogen_input"] / 1000

    print(f"Fraction H2 stored = {round(input_h2_storage / production_h2,4)}")
    print(f"Fraction H2 reconverted = {round(input_h2_gt / production_h2,4)}")

# 2030 Hydrogen scenario
for cy in cys:
    print(f"{cy}")

    path_baseline = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline")][
        ("global", "global", "Path")].values[0]
    path_h2_all = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Hydrogen") & (results_all[("global", "global", "Subcase")] == "all")][
        ("global", "global", "Path")].values[0]

    # Additional re generation
    generic_production_baseline = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline") & (results_all[("global", "global", "Subcase")] == "Baseline")][
        ("global", "electricity", "generic_production")].values[0]
    curtailment_baseline = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline") & (results_all[("global", "global", "Subcase")] == "Baseline")][
        ("global", "electricity", "curtailment")].values[0]
    generic_production_h2 = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Hydrogen") & (results_all[("global", "global", "Subcase")] == "all")][
        ("global", "electricity", "generic_production")].values[0]
    curtailment_h2 = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline") & (results_all[("global", "global", "Subcase")] == "Baseline")][
        ("global", "electricity", "curtailment")].values[0]
    additional_re_generation = (generic_production_h2 - generic_production_baseline)/1000

    print(f"Curtailed fraction of electricity in Baseline = {round((curtailment_baseline)/(curtailment_baseline + generic_production_baseline), 3)}")
    print(f"Curtailed fraction of electricity in H2 all = {round((curtailment_h2)/(generic_production_h2 + curtailment_h2), 3)}")

    annual_production_baseline = get_annual_tec_production(path_baseline)
    annual_production_h2all = get_annual_tec_production(path_h2_all)

    # Nuclear capacity
    c_nuclear = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Baseline")][
        ("tec_sizes", "PowerPlant_Nuclear_existing", "size")].values[0]
    c_electrolyzer = results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Hydrogen") & (results_all[("global", "global", "Subcase")] == "all")][
        ("tec_sizes", "Electrolyser_PEM_offshore", "size")].values[0] + results_all[
        (results_all[("global", "global", "cy")] == cy) & (results_all[("global", "global", "Case")] == "Hydrogen") & (results_all[("global", "global", "Subcase")] == "all")][
        ("tec_sizes", "Electrolyser_PEM", "size")].values[0]
    # Nuclear production baseline
    cf_baseline = annual_production_baseline["PowerPlant_Nuclear_existing"]["electricity_output"] / (c_nuclear*8760)
    # Nuclear production synergies
    cf_h2_all = annual_production_h2all["PowerPlant_Nuclear_existing"]["electricity_output"] / (c_nuclear*8760)
    additional_nuclear_electricity = (annual_production_h2all["PowerPlant_Nuclear_existing"]["electricity_output"] - annual_production_baseline["PowerPlant_Nuclear_existing"]["electricity_output"])/1000

    #H2 production
    production_h2 = (annual_production_h2all["Electrolyser_PEM_offshore"]["hydrogen_output"] + annual_production_h2all["Electrolyser_PEM"]["hydrogen_output"]) / 1000
    cf_electrolyzers = production_h2*1000 / (c_electrolyzer * 8760)
    input_h2_gt = annual_production_h2all["PowerPlant_Gas_existing"]["hydrogen_input"] / 1000
    input_h2_storage = annual_production_h2all["Storage_Hydrogen"]["hydrogen_input"] / 1000
    input_h2_electrolyser = annual_production_h2all["Electrolyser_PEM"]["electricity_input"] / 1000 + annual_production_h2all["Electrolyser_PEM_offshore"]["electricity_input"] / 1000

    print(f"CF_nuclear (Baseline) = {round(cf_baseline,2)}")
    print(f"CF_nuclear (H2all) = {round(cf_h2_all,2)}")
    print(f"CF_electrolyzer (H2all) = {round(cf_electrolyzers,2)}")
    print(f"C_electrolyzer (H2all) = {round(c_electrolyzer,2)}")

    print(f"Fraction H2 stored = {round(input_h2_storage / production_h2,4)}")
    print(f"Fraction H2 reconverted = {round(input_h2_gt / production_h2,4)}")

    print(f"Additional RE: {additional_re_generation}")
    print(f"Additional Nuclear: {additional_nuclear_electricity}")
    print(f"Sum Nuclear + RE: {additional_nuclear_electricity + additional_re_generation}")
    print(f"Electrolyser input: {input_h2_electrolyser}")
    print(f"Fraction of nuclear supply: {additional_nuclear_electricity / input_h2_electrolyser}")
    print(f"H2 produced: {production_h2}")

# 2040 emission reduciton in electricity sector 2030 <> 2040
results_2030 = pd.read_excel(
    "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/Summary_processed.xlsx",
    header=[0, 1, 2], index_col=0)
results_2040 = pd.read_excel(
    "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040/Summary_processed.xlsx",
    header=[0, 1, 2], index_col=0)


for cy in cys:
    print(f"{cy}")

    #Emissions
    emissions_baseline_2030 = results_2030[
        (results_2030[("global", "global", "cy")] == cy) & (results_2030[("global", "global", "Case")] == "Baseline")][
        ("global", "final", "emissions_other")].values[0]
    emissions_baseline_2040 = results_2040[
        (results_2040[("global", "global", "cy")] == cy) & (results_2040[("global", "global", "Case")] == "Baseline")][
        ("global", "final", "emissions_other")].values[0]
    demand_2030 = results_2030[
        (results_2030[("global", "global", "cy")] == cy) & (results_2030[("global", "global", "Case")] == "Baseline")][
        ("global", "electricity", "demand")].values[0]
    demand_2040 = results_2040[
        (results_2040[("global", "global", "cy")] == cy) & (results_2040[("global", "global", "Case")] == "Baseline")][
        ("global", "electricity", "demand")].values[0]

    print(f"Emissions in electricity sector in 2030: {emissions_baseline_2030}")
    print(f"Emissionsreduction in electricity sector is: {(emissions_baseline_2040-emissions_baseline_2030)/emissions_baseline_2030}")

    print(f"Specific emissions in electricity sector in 2030: {emissions_baseline_2030/demand_2030}")
    print(f"Specific emissions in electricity sector in 2040: {emissions_baseline_2040/demand_2040}")
