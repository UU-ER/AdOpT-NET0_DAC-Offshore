import adopt_net0 as adopt
import json
from pathlib import Path
import os
import pandas as pd
import numpy as np
from mes_north_sea.optimization.utilities import *

test = 0
settings = Settings(test=test)
settings.demand_factor = 1
settings.year = 2040
settings.variable_h2_demand = 1
cys = [2008]
co2_tax = [50, 150]

# avg cap factor
total_production = pd.Series()
for cy in [1995, 2008, 2009]:
    time_series = pd.read_csv("./mes_north_sea/clean_data/production_profiles_re/production_profiles_re" + str(cy) + ".csv", index_col=0, header=[0, 1])
    time_series.loc[:, (slice(None), 'total')].sum().sum()
    total_production[str(cy)] = time_series.loc[:, (slice(None), 'total')].sum().sum()/1000000

input_data_path  = Path("mes_north_sea/data_" + str(settings.year))
write_to_network_data(settings)
write_to_technology_data(settings)

# scenarios = {
#     'Hydrogen_H2': 'Hydrogen (no hydrogen offshore)',
#     'Hydrogen_H1': 'Hydrogen (no storage)',
#     'Hydrogen_H4': 'Hydrogen (local use only)',
#     'Hydrogen_Baseline': 'Hydrogen (all)',
#     'All': 'All Pathways',
#     'Hydrogen_H3': 'Hydrogen (no hydrogen onshore)',
#     'ElectricityGrid_all': 'Grid Expansion (all)',
#     'ElectricityGrid_on': 'Grid Expansion (onshore only)',
#     'ElectricityGrid_off': 'Grid Expansion (offshore only)',
#     'ElectricityGrid_noBorder': 'Grid Expansion (no Border)',
#     'RE_only': 'RE only',
#     'Battery_on': 'Battery (onshore only)',
#     'Battery_off': 'Battery (offshore only)',
#     'Battery_all': 'Battery (all)',
#              }

scenarios = {'RE_only': 'RE only',
            'All': 'All Pathways',
             }


for stage in scenarios.keys():
    for cy in cys:
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
            adopt.copy_technology_data(input_data_path, Path(settings.data_path + "technology_data"))
            define_networks(input_data_path, settings)
            define_network_topology(input_data_path, settings, nodes)
            adopt.copy_network_data(input_data_path, Path(settings.data_path + "network_data"))

            define_demand(input_data_path, settings, nodes)

            define_generic_production(input_data_path, settings, nodes)
            define_hydro_inflow(input_data_path, settings)
            define_capacity_factors(input_data_path, settings)
            define_max_renewable_capacities(input_data_path, settings)

            define_imports_exports(input_data_path, settings, nodes)

            m = adopt.ModelHub()
            m.read_data(input_data_path)
            m.data.model_config["reporting"]["save_summary_path"][
                "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250424/"
            m.data.model_config["reporting"]["save_path"][
                "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/20250424/" + str(
                settings.year) + "_cy" + str(settings.climate_year)
            m.data.model_config["reporting"]["case_name"]["value"] = stage + '_costs'

            m = define_charging_efficiencies(settings, nodes, m)

            m.quick_solve()
