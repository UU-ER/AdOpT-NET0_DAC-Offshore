import random
from mes_north_sea.optimization.utilities import *
import os

test = 0
settings = Settings(test=test)
settings.demand_factor = 1
settings.year = 2040
settings.variable_h2_demand = 0
cys = [2009]
co2_tax = [100]
c_permutation = 0.01

# avg cap factor
# total_production = pd.Series()
# for cy in [1995, 2008, 2009]:
#     time_series = pd.read_csv("./mes_north_sea/clean_data/production_profiles_re/production_profiles_re" + str(cy) + ".csv", index_col=0, header=[0, 1])
#     time_series.loc[:, (slice(None), 'total')].sum().sum()
#     total_production[str(cy)] = time_series.loc[:, (slice(None), 'total')].sum().sum()/1000000

project_root = Path(__file__).resolve().parent
data_path = str(project_root / ("mes_north_sea/data_" + str(settings.year)))

write_to_network_data(settings)

write_to_technology_data(settings)
if os.environ.get('HOSTNAME', '').startswith('sd26') or Path('/data/8051917').exists():
    save_path = "/data/8051917/results"
else:
    save_path = "results"

scenarios = {
    'RE_only': 'RE only',
             }

for stage in scenarios.keys():

    if stage in [
    'RE_only']:
        settings.model_h2 = 0
    else:
        settings.model_h2 = 1

    for cy in cys:
        input_data_path = Path(data_path + "_" + str(cy))
        input_data_path.mkdir(parents=True, exist_ok=True)

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

            if settings.test:
                final_save_path = save_path + "/2040_test/"
            else:
                final_save_path = save_path + "/2040/" + str(settings.climate_year)

            Path(final_save_path).mkdir(parents=True, exist_ok=True)

            m.data.model_config["reporting"]["save_summary_path"]["value"] = final_save_path
            m.data.model_config["reporting"]["save_path"]["value"] = final_save_path

            m.data.model_config["reporting"]["case_name"]["value"] = stage + '_costs' + "_cy" + str(
                settings.climate_year) + '_co2_tax' + str(tax)

            m = define_charging_efficiencies(settings, nodes, m)

            m.quick_solve()
