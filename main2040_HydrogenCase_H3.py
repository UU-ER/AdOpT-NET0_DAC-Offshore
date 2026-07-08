import random
from mes_north_sea.optimization.utilities import *

test = 0
settings = Settings(test=test)
settings.demand_factor = 1
settings.year = 2040
settings.variable_h2_demand = 0
cys = [1995, 2008, 2009]
co2_tax = 100
c_permutation = 0.01

# avg cap factor
# total_production = pd.Series()
# for cy in [1995, 2008, 2009]:
#     time_series = pd.read_csv("./mes_north_sea/clean_data/production_profiles_re/production_profiles_re" + str(cy) + ".csv", index_col=0, header=[0, 1])
#     time_series.loc[:, (slice(None), 'total')].sum().sum()
#     total_production[str(cy)] = time_series.loc[:, (slice(None), 'total')].sum().sum()/1000000

data_path = "mes_north_sea/data_" + str(settings.year)
write_to_network_data(settings)
write_to_technology_data(settings)

scenarios = {
    'RE_only': 'RE only',
    'Hydrogen_H3': 'Hydrogen (no hydrogen onshore)',
     }

for cy in cys:

    # Construct All case
    input_data_path = Path(data_path + "_" + str(cy))

    settings.co2_tax = co2_tax

    settings.climate_year = cy

    settings.new_technologies_stage = 'Hydrogen_H3'

    adopt.create_optimization_templates(input_data_path)

    nodes = read_nodes(settings)
    define_topology(settings, input_data_path, nodes)
    define_configuration(input_data_path, settings)

    adopt.create_input_data_folder_template(input_data_path)

    define_node_locations(input_data_path, nodes)
    define_installed_capacities(input_data_path, settings, nodes)
    define_new_technologies(input_data_path, settings, nodes)
    adopt.copy_technology_data(input_data_path, Path(settings.data_path / "technology_data"))
    define_networks(input_data_path, settings)
    define_network_topology(input_data_path, settings, nodes)
    adopt.copy_network_data(input_data_path, Path(settings.data_path / "network_data"))

    define_demand(input_data_path, settings, nodes)

    define_generic_production(input_data_path, settings, nodes)
    define_hydro_inflow(input_data_path, settings)
    define_capacity_factors(input_data_path, settings)
    define_max_renewable_capacities(input_data_path, settings)

    define_imports_exports(input_data_path, settings, nodes)

    m = adopt.ModelHub()
    m.read_data(input_data_path)

    for node in m.data.technology_data["period1"]:
        for tec in m.data.technology_data["period1"][node]:
            print(m.data.technology_data["period1"][node][tec].economics['unit_capex'])
            m.data.technology_data["period1"][node][tec].economics['unit_capex'] = \
                m.data.technology_data["period1"][node][tec].economics['unit_capex'] * random.uniform(
                    1 - c_permutation, 1 + c_permutation)
            print(m.data.technology_data["period1"][node][tec].economics['unit_capex'])

    m = define_charging_efficiencies(settings, nodes, m)
    m.data.model_config["solveroptions"]["threads"]["value"] = 22

    if settings.test:
        m.data.model_config["reporting"]["save_summary_path"][
            "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040_test/"
        m.data.model_config["reporting"]["save_path"][
            "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040_test/"
    else:
        m.data.model_config["reporting"]["save_summary_path"][
            "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040/00_cy" + str(
            settings.climate_year)
        m.data.model_config["reporting"]["save_path"][
            "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040/"

    m.construct_model()
    m.construct_balances()

    for stage in scenarios.keys():
        # Fix respective variables
        new_tecs = pd.read_excel(settings.data_path / 'new_technologies/NewTechnologies_2040.xlsx', index_col=0,
                                 sheet_name='NewTechnologies')

        model = m.model[m.info_solving_algorithms["aggregation_model"]]

        for period in model.periods:
            # TECHNOLOGIES
            for node in model.periods[period].node_blocks:
                for tec in (
                        model.periods[period].node_blocks[node].tech_blocks_active
                ):
                    if not m.data.technology_data[period][node][
                        tec
                    ].existing:
                        if (isinstance(new_tecs[stage][node], float)) or (not tec in new_tecs[stage][node]):
                            model.periods[period].node_blocks[node].tech_blocks_active[tec].var_size.fix(0)
                            print(f"fixing {tec} at node {node}")
                        else:
                            model.periods[period].node_blocks[node].tech_blocks_active[tec].var_size.unfix()
                            print(f"unfixing {tec} at node {node}")

            # NETWORKS
            # H2 networks
            h2_networks = ["hydrogenPipelineOffshore", "hydrogenPipelineOnshore_new",
                           "hydrogenPipelineOnshore_re"]

            for netw in h2_networks:
                if not m.data.network_data[period][netw].existing:
                    b_netw = model.periods[period].network_block[netw]
                    for arc in b_netw.set_arcs:
                        if stage == "RE_only":
                            b_netw.arc_block[arc].var_size.fix(0)
                            print(f"fixing {netw}")

                        else:
                            b_netw.arc_block[arc].var_size.unfix()
                            print(f"unfixing {netw}")


        if settings.test:
            m.data.model_config["reporting"]["save_summary_path"][
                "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040_test/"
            m.data.model_config["reporting"]["save_path"][
                "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040_test/"
        else:
            m.data.model_config["reporting"]["save_summary_path"][
                "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040/00_cy" + str(
                settings.climate_year)
            m.data.model_config["reporting"]["save_path"][
                "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250515/2040/"
        m.data.model_config["reporting"]["case_name"]["value"] = stage + '_costs' + "_cy" + str(
            settings.climate_year) + '_co2_tax' + str(co2_tax)

        m.solve()



