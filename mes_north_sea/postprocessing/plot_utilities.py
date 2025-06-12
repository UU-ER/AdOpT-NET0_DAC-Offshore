from pathlib import Path

import h5py
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from mes_north_sea.postprocessing.utilities import extract_datasets_from_h5_group
from mes_north_sea.preprocessing.utilities import to_latex


def get_data(cy, results, filter_by='cost_total'):
    results_base_cy = results[results["global", "global", "cy"] == cy]
    results_base_cy = results_base_cy.set_index([("global", "global", "Case"), ("global", "global", "Subcase")])
    idx = pd.IndexSlice
    plot_data = results_base_cy.loc[:, idx["global", "final", :]]
    plot_data.columns = plot_data.columns.droplevel([0, 1])
    plot_data.index = plot_data.index.map(lambda x: f"{x[0]} | {x[1]}")

    if "Baseline | Baseline" in plot_data.index:
        baseline = pd.DataFrame(plot_data.loc["Baseline | Baseline"]).T
    else:
        baseline = pd.DataFrame()
    if "All | All" in plot_data.index:
        synergies = pd.DataFrame(plot_data.loc["All | All"]).T
    else:
        synergies = pd.DataFrame()
    others = plot_data.loc[
        (plot_data.index != "Baseline | Baseline") & (plot_data.index != "All | All")
        ]

    return pd.concat([synergies, others.sort_values(by=filter_by, ascending=True), baseline])

def plot_horizontal_bar_plot(ax, df_base, df_others, cols, scaling_factor=1, write_text=True):
    df_plot = df_base[cols].copy()
    df_plot = df_plot * scaling_factor

    # Plot stacked horizontal bar chart
    df_plot.plot(
        kind='barh',
        stacked=True,
        ax=ax,
        colormap='tab20'
    )
    text_pos = 2

    if write_text:
        base_value = df_plot.loc["Baseline | Baseline"].sum()
        reduction = (df_plot.sum(axis=1) - base_value) / base_value * 100

        for idx, (y_pos, perc) in enumerate(zip(df_plot.index, reduction)):
            ax.text(text_pos, idx, f"{perc:+.1f}%", va='center')
        text_pos = text_pos + 10

    if df_others:
        # plot other climate years
        y_positions = range(len(df_plot))
        cy_markers = {1995: 'o', 2008: 'x', 2009: 's'}
        for cy in df_others.keys():
            df_plot = df_others[cy][cols] * scaling_factor

            ax.scatter(
                df_plot.sum(axis=1),
                y_positions,
                color='black',
                zorder=5,
                label='Climate Year Cost',
                marker=cy_markers[cy]
            )
            if write_text:

                base_value = df_plot.loc["Baseline | Baseline"].sum()
                reduction = (df_plot.sum(axis=1) - base_value) / base_value * 100

                for idx, (y_pos, perc) in enumerate(zip(df_plot.index, reduction)):
                    ax.text(text_pos, idx, f"{perc:+.1f}%", va='center')
                text_pos = text_pos + 10

    return ax

def make_figure1():
    load_path = Path("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data")
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/Figure1")
    other_info = pd.read_csv("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/other_info.csv", index_col=0, sep=";")

    for cy in [1995, 2008, 2009]:
        # read nodes
        nodes_all = pd.read_excel(load_path / "nodes/nodes.xlsx", sheet_name='Nodes_used')
        nodes_on = nodes_all[nodes_all['Type'].apply(lambda x: x.startswith('onshore'))]['Node'].values.tolist()
        nodes_off = nodes_all[nodes_all['Type'].apply(lambda x: x.startswith('offshore'))]['Node'].values.tolist()

        # calculate demand
        demand = pd.DataFrame()
        demand_el = pd.read_csv(load_path / "demand" / ("TotalDemand_NT_2030_" + str(cy) + ".csv"), index_col=0)
        demand_h2 = pd.read_excel(load_path / "import_export" / "ImportExport_realistic.xlsx", index_col=0)
        demand["el"] = demand_el.sum()
        demand["h2"] = demand_h2['Export_hydrogen']*8760
        demand.loc["Total", :] = demand.sum()
        demand = demand/1000000

        # calculate generic_production
        all_results = pd.read_excel("//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/cost/Summary_processed.xlsx", header=[0,1,2], index_col=0)
        path_baseline = all_results[(all_results[("global", "global", "cy")] == cy) & (all_results[("global", "global", "Case")] == "Baseline")][("global", "global", "Path")].values[0]
        with h5py.File(path_baseline + '/optimization_results.h5', 'r') as hdf_file:
            ebalance = extract_datasets_from_h5_group(hdf_file["operation/energy_balance"])
        ebalance = pd.DataFrame(ebalance).sum().groupby(level=[1, 2, 3]).sum()
        generic_production = ebalance.loc[:, "electricity", "generic_production"]
        technology_outputs = ebalance.loc[:, "electricity", "technology_outputs"]
        imports = ebalance.loc[:, "electricity", "import"]/1000000
        # exports = ebalance.loc[:, "hydrogen", "export"]/1000000

        other_info = pd.concat([other_info,
                                pd.DataFrame([{
                                    "section": "4.1",
                                    "description": f"import share for cy {cy}",
                                    "value": imports.sum() / demand.loc["Total","el"]
                                }])
                                ])


        # Allocation to type
        re_profile = pd.read_csv(load_path / "production_profiles_re" / ("production_profiles_re" + str(cy) + ".csv"), index_col=0, header=[0,1])
        re_profile = re_profile.sum()
        mask = re_profile.index.get_level_values(1) != "total"
        re_sum = re_profile.loc[:, mask]
        uncurtailed_total = re_sum.groupby(level=0).sum()
        share_used = generic_production / uncurtailed_total
        actual_production = re_sum * re_sum.index.get_level_values(level=0).map(share_used)
        production = actual_production[nodes_on]
        actual_production_off = actual_production[nodes_off]

        other_info = pd.concat([other_info,
                                pd.DataFrame([{
                                    "section": "4.1",
                                    "description": f"curtailment for cy {cy}",
                                    "value": (1 - actual_production.sum() / re_profile[:, "total"].sum())
                                }])
                                ])

        # Allocation to onshore node
        netw_connection_ac = pd.read_csv("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data/networks/pyhub_el_ac_all.csv", sep=";")
        netw_connection_dc = pd.read_csv("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data/networks/pyhub_el_dc_all.csv", sep=";")
        netw_connection = pd.concat([netw_connection_ac, netw_connection_dc])
        netw_connection = netw_connection[netw_connection["s_nom"]>0]

        for n_off in nodes_off:
            con = []
            con.append(netw_connection[netw_connection["node0"] == n_off])
            con.append(netw_connection[netw_connection["node1"] == n_off])
            con = pd.concat(con)
            total_cap = con["s_nom"].sum()
            con["share"] = con["s_nom"] / total_cap

            for idx, n in con.iterrows():
                if n["node0"] == n_off:
                    other_node = n["node1"]
                else:
                    other_node = n["node0"]

                share = n["share"]
                gen = actual_production_off.loc[n_off,:].values[0]
                production.loc[other_node, "Wind offshore"] = gen * share + production.loc[other_node, "Wind offshore"]

        production.name = "prod"

        with h5py.File(path_baseline + '/optimization_results.h5', 'r') as hdf_file:
            tec_operation = extract_datasets_from_h5_group(hdf_file["operation/technology_operation"])
        tec_operation = pd.DataFrame(tec_operation).sum().groupby(level=[1, 2, 3]).sum()
        tec_operation = tec_operation.loc[:,:,"electricity_output"]
        tec_operation.name = "tec"
        storage_sum = tec_operation[tec_operation.index.get_level_values(1).str.startswith("Storage")].groupby(level=0).sum()
        storage_sum.index = pd.MultiIndex.from_arrays([storage_sum.index, ["Hydro"] * len(storage_sum)])
        others_sum = tec_operation[~tec_operation.index.get_level_values(1).str.startswith("Storage")]

        total_production_per_node = pd.concat([production, storage_sum, others_sum])
        total_production_per_node = total_production_per_node/ 1000000
        total_production = total_production_per_node.groupby(level=1).sum()
        total_production.index = pd.MultiIndex.from_arrays([["Total"] * len(total_production), total_production.index])

        final_production = pd.concat([total_production_per_node, total_production])
        final_production.loc["Total"].sum()

        vres_production = final_production.loc["Total"]
        vres_production = vres_production[['Biomass', 'Hydro', 'PV', 'Run of River', 'Wind offshore', 'Wind onshore']].sum()

        other_info = pd.concat([other_info,
                                pd.DataFrame([{
                                    "section": "4.1",
                                    "description": f"vres share for cy {cy}",
                                    "value": vres_production / demand.loc["Total","el"]
                                }])
                                ])

        nodes_plot = nodes_on
        nodes_plot.append("Total")


        # --- Step 1: Prepare final_production ---
        # Pivot so each row is a node and each column is a technology
        fp_wide = final_production.unstack().fillna(0)
        fp_wide.columns.name = None  # remove MultiIndex name on columns
        fp_wide.index.name = 'Node'

        # --- Step 2: Prepare demand ---
        # Make sure index is the same as final_production
        demand = demand.copy()
        demand.index.name = 'Node'

        # --- Step 3: Add a prefix to distinguish between production and demand ---
        fp_wide = fp_wide.add_prefix("prod_")
        demand = demand.add_prefix("demand_")

        # --- Step 4: Combine into one DataFrame with hierarchical columns ---
        combined = pd.concat([fp_wide, demand], axis=1)

        combined = combined.loc[nodes_on]

        # --- Step 5: Plot ---
        nodes = combined.index
        n_nodes = len(nodes)

        fig, ax = plt.subplots(figsize=(n_nodes * 0.6 + 3, 6))

        # Define position: 2 bars per node (production, demand)

        bar_width = 0.3
        x = range(n_nodes)
        x_fp = [i + bar_width / 2 + 0.05 for i in x]
        x_demand = [i - bar_width / 2 - 0.05 for i in x]

        # Split columns by type
        prod_cols = [c for c in combined.columns if c.startswith("prod_")]
        demand_cols = [c for c in combined.columns if c.startswith("demand_")]

        # Stack production
        bottom = [0] * n_nodes

        production_order = [
            "prod_Hydro",
            "prod_Biomass",
            "prod_PV",
            "prod_Run of River",
            "prod_Wind offshore",
            "prod_Wind onshore",
            "prod_PowerPlant_Gas_noh2_existing",
            "prod_PowerPlant_Nuclear_existing",
        ]

        for col in production_order:
            if col in combined:
                ax.bar(x_fp, combined[col], bar_width, label=col, bottom=bottom)
                bottom = [i + j for i, j in zip(bottom, combined[col])]
            else:
                ax.bar(x_fp, [0] * n_nodes, bar_width, label=col, bottom=bottom)
                bottom = [i + j for i, j in zip(bottom, [0] * n_nodes)]

        # Stack demand
        bottom = [0] * n_nodes
        colors=["black", "grey"]
        idx = 0
        for col in demand_cols:
            ax.bar(x_demand, combined[col], bar_width, label=col, bottom=bottom, color=colors[idx])
            bottom = [i + j for i, j in zip(bottom, combined[col])]
            idx = idx+1

        # Final touches
        ax.set_xticks(x)
        ax.set_xticklabels(nodes, rotation=45)
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper right")

        plt.savefig(save_path / str(cy) /f'together.svg')
        plt.close()

        other_info.to_csv("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/other_info.csv",sep=";")

def make_table4():
    load_path = Path("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data")
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/Table4")

    demand_h2 = pd.read_excel(load_path / "import_export" / "ImportExport_realistic.xlsx", index_col=0)
    demand_h2["country"] =  [str(i)[0:2] for i in demand_h2.index]
    demand_h2_per_country = demand_h2.groupby("country").sum()
    demand_h2_per_country = pd.DataFrame(demand_h2_per_country["Export_hydrogen"]) * 8760
    demand_h2_per_country.columns = ["total_demand"]

    emission_factor_h2 = 0.108

    table4 = {}

    for cy in [1995, 2008, 2009]:
        table4[cy] = pd.DataFrame(index=demand_h2_per_country.index)

        # get correct h5 file
        all_results = pd.read_excel("//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/cost/Summary_processed.xlsx", header=[0,1,2], index_col=0)
        path_baseline = all_results[(all_results[("global", "global", "cy")] == cy) & (all_results[("global", "global", "Case")] == "Baseline")][("global", "global", "Path")].values[0]

        # production h2
        with h5py.File(path_baseline + '/optimization_results.h5', 'r') as hdf_file:
            ebalance = extract_datasets_from_h5_group(hdf_file["operation/energy_balance"])
        ebalance = pd.DataFrame(ebalance).sum()
        try:
            # values from here are slightly different from summary, bc in summary they are rounded.
            ebalance_h2 = pd.DataFrame(ebalance.loc["period1", :, "hydrogen", "export"], columns=["total_production"])
            ebalance_h2["country"] = [str(i)[0:2] for i in ebalance_h2.index]
            production_h2_per_country = ebalance_h2.groupby("country").sum()
            residual_demand_h2_per_country = demand_h2_per_country["total_demand"] - production_h2_per_country["total_production"]
            table4[cy]["H2 production emissions"] = residual_demand_h2_per_country * (emission_factor_h2 * 10**-6)
        except:
            table4[cy]["H2 production emissions"] = demand_h2_per_country["total_demand"] * (emission_factor_h2 * 10**-6)
        table4[cy].loc["total", "H2 production emissions"] = table4[cy]["H2 production emissions"].sum()

        # electricity emissions
        with h5py.File(path_baseline + '/optimization_results.h5', 'r') as hdf_file:
            tec_operation = extract_datasets_from_h5_group(hdf_file["operation/technology_operation"])
        tec_operation = pd.DataFrame(tec_operation).sum().groupby(level=[1, 2, 3]).sum()
        tec_operation_emissions = pd.DataFrame(tec_operation.loc[:,:,"emissions_pos"]).groupby(level=[0]).sum()

        tec_operation_emissions["country"] = [str(i)[0:2] for i in tec_operation_emissions.index]
        tec_operation_per_country = tec_operation_emissions.groupby("country").sum() / 1000000
        table4[cy]["electricity production emissions"] = tec_operation_per_country
        table4[cy].loc["total", "electricity production emissions"] = table4[cy]["electricity production emissions"].sum()

        # net imports
        with h5py.File(path_baseline + '/optimization_results.h5', 'r') as hdf_file:
            netw_operation = extract_datasets_from_h5_group(hdf_file["operation/networks"])
        with h5py.File(path_baseline + '/optimization_results.h5', 'r') as hdf_file:
            netw_design = extract_datasets_from_h5_group(hdf_file["design/networks"])
        netw_design = pd.DataFrame(netw_design)
        arc_keys = netw_design.melt()
        arc_keys.columns = ["period", "network", "arc", "variable", "value"]
        arc_keys = arc_keys[["arc", "variable", "value"]]
        arc_keys = arc_keys[arc_keys["variable"].isin(['fromNode', 'toNode'])]
        arc_keys["value"] = arc_keys["value"].apply(lambda x: x.decode() if isinstance(x, bytes) else x)
        arc_keys = arc_keys.drop_duplicates(["arc", "variable"]).pivot(index="arc", columns="variable")
        arc_keys = arc_keys.loc[:, "value"]

        netw_operation = pd.DataFrame(netw_operation).sum().groupby(level=[2,3]).sum()
        netw_operation_per_arc = pd.DataFrame(netw_operation.loc[:, "flow"], columns = ["value"])
        netw_operation_per_arc = netw_operation_per_arc.merge(arc_keys, left_index=True, right_index=True)
        netw_operation_per_arc["fromCountry"] = [str(i)[0:2] for i in netw_operation_per_arc["fromNode"]]
        netw_operation_per_arc["toCountry"] = [str(i)[0:2] for i in netw_operation_per_arc["toNode"]]
        netw_operation_cross_boundary = netw_operation_per_arc[netw_operation_per_arc["toCountry"] != netw_operation_per_arc["fromCountry"]]
        netw_operation_cross_boundary = netw_operation_cross_boundary[["fromCountry", "toCountry", "value"]].groupby(["fromCountry", "toCountry"]).sum()
        netw_operation_cross_boundary = netw_operation_cross_boundary.reset_index()
        countries = netw_operation_per_arc["toCountry"].drop_duplicates().to_list()

        for c in countries:
            imports = netw_operation_cross_boundary[netw_operation_cross_boundary["toCountry"] == c]["value"].sum()
            exports = netw_operation_cross_boundary[netw_operation_cross_boundary["fromCountry"] == c]["value"].sum()
            table4[cy].loc[c, "Net imports (within system)"] = (imports-exports)/1000000

        # electricity imports
        el_imports = pd.DataFrame(ebalance.loc["period1", :, "electricity", "import"], columns=["total_imports"])
        el_imports["country"] = [str(i)[0:2] for i in el_imports.index]
        table4[cy]["imports (from outside system)"] = el_imports.groupby("country").sum()/1000000
        table4[cy].loc["total", "imports (from outside system)"] = table4[cy]["imports (from outside system)"].sum()

        # re-share
        el_demand = pd.DataFrame(ebalance.loc["period1", :, "electricity", "demand"], columns=["el_demand"])
        el_demand["country"] = [str(i)[0:2] for i in el_demand.index]
        el_demand = el_demand.groupby("country").sum()

        generic_production = pd.DataFrame(ebalance.loc["period1", :, "electricity", "generic_production"], columns=["generic_production"])
        generic_production["country"] = [str(i)[0:2] for i in generic_production.index]
        generic_production = generic_production.groupby("country").sum()

        other_re = tec_operation.loc[:, ["Storage_PumpedHydro_Closed_existing", "Storage_PumpedHydro_Open_existing", "Storage_PumpedHydro_Reservoir_existing"], "electricity_output"]
        other_re = pd.DataFrame(other_re.groupby(level=0).sum(), columns=["other_re"])
        other_re["country"] = [str(i)[0:2] for i in other_re.index]
        other_re = other_re.groupby("country").sum()

        final_share = pd.merge(el_demand, generic_production, left_index=True, right_index=True)
        final_share = pd.merge(final_share, other_re, left_index=True, right_index=True, how="outer").fillna(0)
        final_share["re_share"] = (final_share["other_re"] + final_share["generic_production"]) / final_share["el_demand"] *100

        table4[cy]["re_share"] = final_share["re_share"]

        table4[cy].to_excel(save_path / f"table4{str(cy)}.xlsx")

        table4[cy]["re_share"] = [str(round(i,1)) + "\% "for i in table4[cy]["re_share"].to_list()]
        table4[cy]["National goal"] = ["37.4\%", "80\%", "117\%$^\mathrm{a}$", "70\%", "100\%", "95\%$^\mathrm{b}$", ""]
        table4[cy]["Source"] = ["\cite{IEAInternationalEnergyAgency2022}", "\cite{Bundesregierung2023}", "\cite{Energistyrelsen2023}", "\cite{MinistryofEconomicAffairsandClimatePolicy2019}", "\cite{IEAInternationalEnergyAgency2022a}", "\cite{HMGovernment2022}", ""]
        to_latex(table4[cy], "", save_path / f"table4{str(cy)}.txt", rounding=2)

def make_table_s5():
    load_path = Path("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data")
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/TableS5-ElectricityDemand2030")

    demand_el = pd.DataFrame()
    for cy in [1995, 2008, 2009]:
        demand = pd.read_csv(load_path / "demand" / ("TotalDemand_NT_2030_" + str(cy) + ".csv"), index_col=0)
        demand_per_node = demand.sum().reset_index()
        demand_per_node.columns = ["node", "value"]
        demand_per_node["country"] = [n[0:2] for n in demand_per_node["node"].to_list()]
        demand_per_country = demand_per_node[["country", "value"]].groupby("country").sum()
        demand_el[cy] = demand_per_country*10**-6
    demand_el["Neumann"] = [131, 730, 50, 186, 113, 434]
    demand_el["Eurostat"] = [81, 497, 31, 107, 116, 295]


    demand_el.to_excel(save_path / f"tableS5.xlsx")
    to_latex(demand_el, "", save_path / f"tableS5.txt", rounding=0)

def make_table_s6():
    load_path = Path("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data")
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/TableS6-ElectricityDemand2040")

    demand_el = pd.DataFrame()
    for cy in [1995, 2008, 2009]:
        demand = pd.read_csv(load_path / "demand" / ("TotalDemand_NT_2040_" + str(cy) + ".csv"), index_col=0)
        demand_per_node = demand.sum().reset_index()
        demand_per_node.columns = ["node", "value"]
        demand_per_node["country"] = [n[0:2] for n in demand_per_node["node"].to_list()]
        demand_per_country = demand_per_node[["country", "value"]].groupby("country").sum()
        demand_el[cy] = demand_per_country*10**-6

    demand_el.to_excel(save_path / f"tableS6.xlsx")
    to_latex(demand_el, "", save_path / f"tableS6.txt", rounding=0)

def make_table_s7():
    load_path = Path("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data")
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/TableS7-HydrogenDemand")

    demand = pd.DataFrame()

    demand_h2 = pd.read_excel(load_path / "import_export" / "ImportExport_realistic.xlsx", index_col=0)
    demand_h2 = pd.DataFrame(demand_h2['Export_hydrogen'] * 8760)
    demand_h2["country"] = [n[0:2] for n in demand_h2.index]
    demand_h2=demand_h2.groupby("country").sum()/ 1000000
    demand[2030] = demand_h2

    demand_h2 = pd.read_excel(load_path / "import_export" / "ImportExport_realistic_2040.xlsx", index_col=0)
    demand_h2 = pd.DataFrame(demand_h2['Export_hydrogen'] * 8760)
    demand_h2["country"] = [n[0:2] for n in demand_h2.index]
    demand_h2=demand_h2.groupby("country").sum()/ 1000000
    demand[2040] = demand_h2

    demand.to_excel(save_path / f"tableS7.xlsx")
    to_latex(demand, "", save_path / f"tableS7.txt", rounding=0)

def make_table_s8():
    load_path = Path("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data")
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/TableS8-VRES-generation")

    capacities_per_node = pd.read_csv(load_path/ 'installed_capacities/capacities_node.csv', index_col=0)
    capacities_per_country = capacities_per_node[['Country', 'Technology', 'Capacity our work']].groupby(['Country', 'Technology']).sum().reset_index()

    replacements = {
        'Solar': 'PV',
        'Biofuels': 'Biomass',
        'Wind Onshore': 'Wind onshore',
        'Wind Offshore': 'Wind offshore',
        'Hydro - Run of River (Turbine)': 'Run of River'
    }
    capacities_per_country['Technology'] = capacities_per_country['Technology'].replace(replacements)
    capacities_per_country = capacities_per_country[capacities_per_country['Technology'].isin([i[1] for i in replacements.items()])]
    capacities_per_country.columns = ["country", "Source", "cap"]
    capacities_per_country = capacities_per_country.set_index(["country", "Source"])

    vres_per_country = pd.DataFrame()
    for cy in [1995, 2008, 2009]:
        vres_profiles = pd.read_csv(load_path / "production_profiles_re" / f"production_profiles_re{cy}.csv", sep=",", header=[0,1], index_col=0)
        # generation
        vres_per_node = pd.DataFrame(vres_profiles.sum() *10**-6).reset_index()
        vres_per_node.columns = ["node", "Source", cy]
        vres_per_node["country"] = [i[0:2] for i in vres_per_node["node"]]
        vres_per_country[cy] = vres_per_node[["country", "Source", cy]].groupby(["country", "Source"]).sum()

    cfs = vres_per_country.copy()
    cfs["capacity"] = capacities_per_country

    #cfs
    for cy in [1995, 2008, 2009]:
        cfs[cy] = cfs[cy] / (cfs["capacity"]*8760*10**-6)
    cfs.drop(columns=["capacity"], inplace=True)

    vres_per_country.index = pd.MultiIndex.from_arrays([vres_per_country.index.get_level_values(0),
                                                        vres_per_country.index.get_level_values(1),
                                                        ["generation"] * len(vres_per_country)],
                                                       names=["country", "Source", "type"])

    cfs.index = pd.MultiIndex.from_arrays([cfs.index.get_level_values(0),
                                                        cfs.index.get_level_values(1),
                                                        ["capacity factor"] * len(vres_per_country)],
                                                       names=["country", "Source", "type"])

    final_table = pd.concat([vres_per_country, cfs])

    final_table = final_table.reset_index().melt(id_vars=["country", "Source", "type"]).pivot(index=["Source", "type", "variable"], columns=["country"])
    final_table.to_excel(save_path / f"tableS8.xlsx")
    to_latex(final_table, "", save_path / f"tableS8.txt", rounding=2)

def make_cost_reduction_figure(case, figure_name, plot_other_cys=False):

    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/") / figure_name

    results_all = pd.read_excel(
        "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/Summary_processed.xlsx",
        header=[0, 1, 2], index_col=0)
    results_filtered = results_all[
        (results_all["global", "global", "Case"].isin([case, "Baseline", "All"])) &
        (results_all["global", "global", "objective"] == "min costs")
    ]
    cys = [1995, 2008, 2009]

    for base_cy in cys:
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(30, 4))

        plot_data_base_cy = get_data(base_cy, results_filtered)
        plot_data_other_cys = {}
        if plot_other_cys:
            for cy in [x for x in cys if x != base_cy]:
                plot_data_other_cys[cy] = get_data(cy, results_filtered)

        ax1 = plot_horizontal_bar_plot(ax1, plot_data_base_cy, plot_data_other_cys, ['hydrogen_costs_smr', 'cost_existing_system', 'cost_new_system'], scaling_factor=10**-9)
        ax1.axvline(x=plot_data_base_cy.loc[:, "cost_total"].max() * 10**-9, color='red', linestyle='--')
        ax1.set_xlim(0, 40)
        ax1.legend().set_visible(False)

        ax2 = plot_horizontal_bar_plot(ax2, plot_data_base_cy, plot_data_other_cys, ['emissions_smr', 'emissions_other'], scaling_factor=10**-6)
        ax2.axvline(x=plot_data_base_cy.loc[:, "emissions_total"].max() * 10**-6, color='red', linestyle='--')
        ax2.set_xlim(0, 120)
        ax2.legend().set_visible(False)
        ax2.set_yticklabels([])

        ax3 = plot_horizontal_bar_plot(ax3, plot_data_base_cy, plot_data_other_cys, ['abatement_cost'], scaling_factor=-1)
        ax3.axvline(x=-plot_data_base_cy.loc[:, "abatement_cost"].max(), color='red', linestyle='--')
        ax3.set_xlim(-300, 0)
        ax3.legend().set_visible(False)
        ax3.set_yticklabels([])

        plt.tight_layout()

        if plot_other_cys:
            plt.savefig(save_path / f'cost_reduction_{base_cy}_with_other_cys.svg')
        else:
            plt.savefig(save_path / f'cost_reduction_{base_cy}.svg')

        plt.close()

def make_emission_reduction_figure(case, figure_name, plot_other_cys=False):

    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/") / figure_name

    results_all = pd.read_excel(
        "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/Summary_processed.xlsx",
        header=[0, 1, 2], index_col=0)
    results_filtered = results_all[
        (results_all["global", "global", "Case"].isin([case, "All"])) &
        (results_all["global", "global", "objective"] == "min emissions")
    ]
    results_baseline = results_all[results_all["global", "global", "Case"] == "Baseline"]

    results_filtered = pd.concat([results_filtered, results_baseline])

    cys = [1995, 2008, 2009]

    for base_cy in cys:
        fig, (ax1) = plt.subplots(1, 1, figsize=(10, 4))

        plot_data_base_cy = get_data(base_cy, results_filtered, filter_by="emissions_total")
        plot_data_other_cys = {}
        if plot_other_cys:
            for cy in [x for x in cys if x != base_cy]:
                plot_data_other_cys[cy] = get_data(cy, results_filtered)

        ax1 = plot_horizontal_bar_plot(ax1, plot_data_base_cy, plot_data_other_cys, ['emissions_smr', 'emissions_other'], scaling_factor=10**-6)
        ax1.axvline(x=plot_data_base_cy.loc[:, "emissions_total"].max() * 10**-6, color='red', linestyle='--')
        ax1.set_xlim(0, 120)
        ax1.legend().set_visible(False)

        plt.tight_layout()

        if plot_other_cys:
            plt.savefig(save_path / f'cost_reduction_{base_cy}_with_other_cys.svg')
        else:
            plt.savefig(save_path / f'cost_reduction_{base_cy}.svg')

        plt.close()

def make_cost_at_emission_target_figure(case, figure_name, plot_other_cys=False):
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/") / figure_name

    results_all = pd.read_excel(
        "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/Summary_processed.xlsx",
        header=[0, 1, 2], index_col=0)
    results_filtered = results_all[
        (results_all["global", "global", "Case"].isin([case])) &
        (results_all["global", "global", "objective"] == "min cost at emission limit")
    ]

    cys = [1995, 2008, 2009]

    for base_cy in cys:
        fig, (ax1) = plt.subplots(1, 1, figsize=(10, 6))

        plot_data_base_cy = get_data(base_cy, results_filtered, filter_by="emissions_total")
        plot_data_base_cy["emission_reduction_percentage"] = round(plot_data_base_cy["emission_reduction"] / (plot_data_base_cy["emissions_total"] + plot_data_base_cy["emission_reduction"]),2)
        plot_data_base_cy.index = [f"{str(round(i*100,0))}% | {idx}" for idx, i in plot_data_base_cy["emission_reduction_percentage"].items()]


        plot_data_other_cys = {}
        if plot_other_cys:
            for cy in [x for x in cys if x != base_cy]:
                plot_data_other_cys[cy] = get_data(cy, results_filtered)
                plot_data_other_cys[cy]["emission_reduction_percentage"] = round(plot_data_other_cys[cy]["emission_reduction"] / (
                            plot_data_other_cys[cy]["emissions_total"] + plot_data_other_cys[cy]["emission_reduction"]), 2)
                plot_data_other_cys[cy].index = [f"{str(round(i*100,0))}% | {idx}" for idx, i in plot_data_other_cys[cy]["emission_reduction_percentage"].items()]

        ax1 = plot_horizontal_bar_plot(ax1, plot_data_base_cy, plot_data_other_cys, ['abatement_cost'], scaling_factor=-1, write_text=False)
        # ax1.axvline(x=plot_data_base_cy.loc[:, "emissions_total"].max() * 10**-6, color='red', linestyle='--')
        # ax1.set_xlim(0, 120)
        ax1.legend().set_visible(False)

        plt.tight_layout()

        if plot_other_cys:
            plt.savefig(save_path / f'cost_reduction_{base_cy}_with_other_cys.svg')
        else:
            plt.savefig(save_path / f'cost_reduction_{base_cy}.svg')

        plt.close()

def make_figure3(plot_other_cys):
    make_cost_reduction_figure("Grid Expansion", "Figure3_cost_grid", plot_other_cys)

def make_figure5(plot_other_cys):
    make_cost_reduction_figure("Storage", "Figure5_cost_storage", plot_other_cys)

def make_figure8(plot_other_cys):
    make_cost_reduction_figure("Hydrogen", "Figure8_cost_hydrogen", plot_other_cys)

def make_figure2(plot_other_cys):
    make_emission_reduction_figure("Grid Expansion", "Figure2_emission_grid", plot_other_cys)

def make_figure4(plot_other_cys):
    make_emission_reduction_figure("Storage", "Figure4_emission_storage", plot_other_cys)

def make_figure7(plot_other_cys):
    make_emission_reduction_figure("Hydrogen", "Figure7_emission_hydrogen", plot_other_cys)

def make_figure6(plot_other_cys):
    make_cost_at_emission_target_figure("Storage", "Figure6_cost_at_emission_storage", plot_other_cys)

def make_figure9(plot_other_cys):
    make_cost_at_emission_target_figure("Hydrogen", "Figure9_cost_at_emission_hydrogen", plot_other_cys)

def make_tablesS15ff():
    load_path = Path("C:/Users/6574114/PycharmProjects/PyHubProductive/mes_north_sea/clean_data")
    save_path = Path("C:/Users/6574114/OneDrive - Universiteit Utrecht/PhD Jan/Papers/DOSTA - HydrogenOffshore/00_Figures/2025-06-01/TableS15-S17_InstalledCapacities2030")

    all_results = pd.read_excel(
        "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2030/Summary_processed.xlsx",
        header=[0, 1, 2], index_col=0)
    results_filtered = all_results[
        (all_results["global", "global", "objective"] == "min costs")
    ]
    all_results = all_results.set_index([("global", "global", "Case"), ("global", "global", "Subcase")])
    all_results.index = all_results.index.map(lambda x: f"{x[0]} | {x[1]}")

    arc_length_ac = pd.read_csv(load_path / "networks" / "pyhub_el_ac_all.csv", sep=";")
    arc_length_dc = pd.read_csv(load_path / "networks" / "pyhub_el_dc_all_2040.csv", sep=";")
    arc_l = pd.concat(
        [arc_length_ac[["node0", "node1", "length"]], arc_length_dc[["node0", "node1", "length"]]]).drop_duplicates()
    arc_l["arc_id"] = arc_l["node0"] + arc_l["node1"]
    arc_l["country0"] = [str(a)[0:2] for a in arc_l["node0"]]
    arc_l["country1"] = [str(a)[0:2] for a in arc_l["node1"]]
    arc_l["country_connection"] = arc_l["country0"] + arc_l["country1"]

    index_map = {
        'T-1 (only onshore) ': 'Grid Expansion | onshore only',
        'T-2 (only offshore) ': 'Grid Expansion | offshore only',
        'T-3 (no border cross) ': 'Grid Expansion | no Border',
        'T-All ': 'Grid Expansion | all',
        'S-1 (only onshore) ': 'Storage | onshore only',
        'S-2 (only offshore) ': 'Storage | offshore only',
        'S-All-HPE': 'Storage | all HP',
        'S-All ': 'Storage | all',
        'H-1 (only onshore) ': 'Hydrogen | no hydrogen offshore',
        'H-2 (only offshore) ': 'Hydrogen | no hydrogen onshore',
        'H-3 (no storage) ': 'Hydrogen | no storage',
        'H-4 (only local use) ': 'Hydrogen | local use only',
        'H-All ': 'Hydrogen | all',
        'Synergies ': 'All | All',
    }

    for cy in [1995, 2008, 2009]:

        capacities = pd.DataFrame(index = index_map.keys())
        results_cy = all_results[(all_results[("global", "global", "cy")] == cy)]
        capacities_raw = results_cy.loc[:, ["tec_sizes"]]

        for scenario in index_map:
            result_path = results_cy.loc[index_map[scenario],("global", "global", "Path")]
            with h5py.File(result_path + '/optimization_results.h5', 'r') as hdf_file:
                network_sizes = extract_datasets_from_h5_group(hdf_file["design/networks/period1"])
            network_sizes_df = pd.DataFrame(network_sizes).T
            network_sizes_df = network_sizes_df.unstack(level=2)
            network_sizes_df.columns = network_sizes_df.columns.droplevel(0)
            network_sizes_df = pd.DataFrame(network_sizes_df['size']).reset_index()
            network_sizes_df.columns = ["network", "arc_id", "size"]
            network_sizes_df = network_sizes_df.merge(arc_l, right_on="arc_id", left_on="arc_id")
            network_sizes_df["size_GWkm"] = network_sizes_df["size"] /1000 * network_sizes_df["length"]

            network_sizes_aggregated = network_sizes_df[["size_GWkm", "network"]].groupby(["network"]).sum()
            network_sizes_aggregated = network_sizes_aggregated["size_GWkm"]

            if "hydrogenPipelineOffshore" in network_sizes_aggregated.index:
                capacities.loc[scenario, "Pipeline offshore (GWkm)"] = network_sizes_aggregated["hydrogenPipelineOffshore"]
            else:
                capacities.loc[scenario, "Pipeline offshore (GWkm)"] = np.nan

            if "hydrogenPipelineOnshore_new" in network_sizes_aggregated.index:
                capacities.loc[scenario, "Pipeline onshore (new) (GWkm)"] = network_sizes_aggregated["hydrogenPipelineOnshore_new"]
            else:
                capacities.loc[scenario, "Pipeline onshore (new) (GWkm)"] = np.nan

            if "hydrogenPipelineOnshore_re" in network_sizes_aggregated.index:
                capacities.loc[scenario, "Pipeline onshore (re) (GWkm)"] = network_sizes_aggregated["hydrogenPipelineOnshore_re"]
            else:
                capacities.loc[scenario, "Pipeline onshore (re) (GWkm)"] = np.nan

            if "electricityAC" in network_sizes_aggregated.index:
                capacities.loc[scenario, "AC (GWkm)"] = network_sizes_aggregated["electricityAC"]
            else:
                capacities.loc[scenario, "AC (GWkm)"] = np.nan

            if "electricityDC" in network_sizes_aggregated.index:
                capacities.loc[scenario, "DC (GWkm)"] = network_sizes_aggregated["electricityDC"]
            else:
                capacities.loc[scenario, "DC (GWkm)"] = np.nan

            if scenario == "S-All-HPE":
                capacities.loc[scenario, "Battery offshore (GWh)"] = capacities_raw.loc[index_map[scenario], (
                'tec_sizes', 'Storage_Battery_new_HP', 'size')] / 1000
                capacities.loc[scenario, "Battery onshore (GWh)"] = capacities_raw.loc[index_map[scenario], (
                'tec_sizes', 'Storage_Battery_Offshore_HP', 'size')] / 1000
            else:
                capacities.loc[scenario, "Battery onshore (GWh)"] = capacities_raw.loc[index_map[scenario], (
                'tec_sizes', 'Storage_Battery_new', 'size')] / 1000
                capacities.loc[scenario, "Battery offshore (GWh)"] = capacities_raw.loc[index_map[scenario], (
                'tec_sizes', 'Storage_Battery_Offshore', 'size')] / 1000

            capacities.loc[scenario, "Electrolyzer offshore (GW)"] = capacities_raw.loc[index_map[scenario], ('tec_sizes', 'Electrolyser_PEM_offshore', 'size')]/1000
            capacities.loc[scenario, "Electrolyzer onshore (GW)"] = capacities_raw.loc[index_map[scenario], ('tec_sizes', 'Electrolyser_PEM', 'size')]/1000

            capacities.loc[scenario, "Fuel Cell (GWh)"] = capacities_raw.loc[index_map[scenario], ('tec_sizes', 'FuelCell', 'size')]/1000
            capacities.loc[scenario, "H2 storage (GWh)"] = capacities_raw.loc[index_map[scenario], ('tec_sizes', 'Storage_Hydrogen', 'size')]/1000

            to_latex(capacities, "", save_path / f"tableS15-17_cy{cy}.txt", rounding=2)

