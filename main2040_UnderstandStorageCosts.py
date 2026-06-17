import random
from mes_north_sea.optimization.utilities import *
import pyomo.environ as pyo

test = 0
settings = Settings(test=test)
settings.demand_factor = 1
settings.year = 2040
settings.variable_h2_demand = 0
cys = [1995, 2008, 2009]
co2_tax = [100]
c_permutation = 0.01

# avg cap factor
# total_production = pd.Series()
# for cy in [1995, 2008, 2009]:
#     time_series = pd.read_csv("./mes_north_sea/clean_data/production_profiles_re/production_profiles_re" + str(cy) + ".csv", index_col=0, header=[0, 1])
#     time_series.loc[:, (slice(None), 'total')].sum().sum()
#     total_production[str(cy)] = time_series.loc[:, (slice(None), 'total')].sum().sum()/1000000

result_path = Path(r"A:\ResearchData\MESNS\Storage_costs2040")

data_path = "mes_north_sea/data_" + str(settings.year)
write_to_network_data(settings)
write_to_technology_data(settings)

scenarios = {
    'All': 'All Pathways',
             }

all_costs = {
    1995: 40213568070,
    2008: 32076678356,
    2009: 35126262404,
}



for stage in scenarios.keys():

    settings.model_h2 = 1

    for cy in cys:
        input_data_path = Path(data_path + "_" + str(cy))

        for tax in co2_tax:
            settings.co2_tax = tax

            settings.climate_year = cy

            settings.new_technologies_stage = stage

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

            # Set storage cost to zero:
            for node in m.data.technology_data["period1"]:
                if "Storage_Battery_new" in m.data.technology_data["period1"][node]:
                    m.data.technology_data["period1"][node]["Storage_Battery_new"].economics['unit_capex'] = 0
                if "Storage_Battery_Offshore" in m.data.technology_data["period1"][node]:
                    m.data.technology_data["period1"][node]["Storage_Battery_Offshore"].economics['unit_capex'] = 0


            if settings.test:
                m.data.model_config["reporting"]["save_summary_path"][
                    "value"] = result_path
                m.data.model_config["reporting"]["save_path"][
                    "value"] = result_path
            else:
                m.data.model_config["reporting"]["save_summary_path"][
                    "value"] = f"{result_path}" + str(
                    settings.climate_year)
                m.data.model_config["reporting"]["save_path"][
                    "value"] = f"{result_path}"
            m.data.model_config["reporting"]["case_name"]["value"] = stage + '_costs' + "_cy" + str(
                settings.climate_year) + '_co2_tax' + str(tax)

            m = define_charging_efficiencies(settings, nodes, m)

            m.construct_model()
            m.construct_balances()

            # Make 1 GW constraint on size
            def init_storage_constraint(const):
                storage_capacity = sum(
                    sum(
                    sum(
                        m.model["full"].periods[period].node_blocks[node].tech_blocks_active[tec].var_size
                        for tec in ["Storage_Battery_new", "Storage_Battery_Offshore"]
                        if (tec in m.model["full"].periods[period].node_blocks[node].tech_blocks_active)
                    )
                    for node in m.model["full"].set_nodes
                )
                    for period in m.model["full"].periods
                )
                return (
                    storage_capacity <= 1000
                )


            m.model["full"].const_storage_constraint = pyo.Constraint(rule=init_storage_constraint)

            # Formulate constaint on total npv
            m.model["full"].const_npv = pyo.Constraint(expr=m.model["full"].var_npv <= all_costs[cy])



            m.solve()
