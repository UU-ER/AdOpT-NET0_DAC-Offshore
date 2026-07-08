import adopt_net0 as adopt
import json
from pathlib import Path
import os
import pandas as pd
import numpy as np
from mes_north_sea.optimization.utilities import *

test = 1
settings = Settings(test=test)
settings.demand_factor = 1
settings.year = 2030

settings.start_date = '05-01 00:00'
settings.end_date = '05-02 23:00'
settings.only_belgium = 1

input_data_path  = Path("mes_north_sea/data_" + str(settings.year))
write_to_network_data(settings)
write_to_technology_data(settings)



# scenarios = {'Baseline': 'Baseline',
#               'Battery_on': 'Battery (onshore only)',
#               'Battery_off': 'Battery (offshore only)',
#               'Battery_all': 'Battery (all)',
#               'Battery_all_HP': 'Battery (all, high power-energy-ratio)',
#               'ElectricityGrid_all': 'Grid Expansion (all)',
#               'ElectricityGrid_on': 'Grid Expansion (onshore only)',
#               'ElectricityGrid_off': 'Grid Expansion (offshore only)',
#               'ElectricityGrid_noBorder': 'Grid Expansion (no Border)',
#               'Hydrogen_Baseline': 'Hydrogen (all)',
#               'Hydrogen_H1': 'Hydrogen (no storage)',
#               'Hydrogen_H2': 'Hydrogen (no hydrogen offshore)',
#               'Hydrogen_H3': 'Hydrogen (no hydrogen onshore)',
#               'Hydrogen_H4': 'Hydrogen (local use only)',
#               'All': 'All Pathways'
#              }

scenarios = {'Baseline': 'Baseline',
             }


for stage in scenarios.keys():
    for cy in [2008]:
        settings.climate_year = cy

        settings.new_technologies_stage = stage

        adopt.create_optimization_templates(input_data_path)

        nodes = read_nodes(settings)
        define_topology(settings, input_data_path, nodes)
        define_configuration(input_data_path, settings)

        with open(input_data_path / "ConfigModel.json", "r") as json_file:
            configuration = json.load(json_file)
        configuration["optimization"]["typicaldays"]["N"]["value"] = 0
        with open(input_data_path / "ConfigModel.json", "w") as json_file:
            json.dump(configuration, json_file, indent=4)

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

        define_imports_exports(input_data_path, settings, nodes)

        m = adopt.ModelHub()
        m.read_data(input_data_path)
        m.data.model_config["reporting"]["save_summary_path"][
            "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/test_clustering"
        m.data.model_config["reporting"]["save_path"][
            "value"] = "//Soliscom.uu.nl/geo/USERS/StaffUsers/6574114/EhubResults/MES NorthSea/test_clustering"
        m.data.model_config["reporting"]["case_name"]["value"] = "clustering_off"

        m = define_charging_efficiencies(settings, nodes, m)

        m.quick_solve()
