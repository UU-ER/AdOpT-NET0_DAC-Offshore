import adopt_net0 as adopt
import json
from pathlib import Path
import os
import pandas as pd
import numpy as np
from mes_north_sea.optimization.utilities import *

test = 1
input_data_path  = Path("mes_north_sea/data_2030")

settings = Settings(test=1)

nodes = read_nodes(settings)

# Create template files (comment these lines if already defined)
adopt.create_optimization_templates(path)
adopt.create_montecarlo_template_csv(path)

# Create folder structure (comment these lines if already defined)
adopt.create_input_data_folder_template(path)

# Copy technology and network data into folder (comment these lines if already defined)
adopt.copy_technology_data(path, "path to tec data")
adopt.copy_network_data(path, "path to network data")

# Read climate data and fill carried data (comment these lines if already defined)
adopt.load_climate_data_from_api(path)
adopt.fill_carrier_data(path, value=0)

# Construct and solve the model
pyhub = adopt.ModelHub()
pyhub.read_data(path)
pyhub.quick_solve()

# Add values of (part of) the parameters and variables to the summary file
add_values_to_summary(Path("path to summary file"))
