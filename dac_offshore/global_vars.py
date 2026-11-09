from pathlib import Path

# # REDUCED RUNS
# BASELINE_SCENARIO = ['No_DAC']
# DAC_SCENARIOS = ['DAC']
# SCENARIOS = BASELINE_SCENARIO + DAC_SCENARIOS
# CLIMATE_YEARS = [1995]
# CO2_PRICE = 100
# GAS_PRICE = 40
# NEGATIVE_FRACTIONS = [0.05]
# RUN_ID = 1

# FULL SETTINGS
BASELINE_SCENARIO = ['No_DAC']
DAC_SCENARIOS = ['DAC', 'Onshore_DAC_only', 'Offshore_DAC_only']
DAC_ALL = ['DAC']
SCENARIOS = BASELINE_SCENARIO + DAC_SCENARIOS
CLIMATE_YEARS = [1995, 2008, 2009]
CO2_PRICE = 189
GAS_PRICE = 72
NEGATIVE_FRACTIONS = [0.05, 0.1, 0.15, 0.2]
RUN_ID = 1
TEST=True

# Results folders, selected with --run_on
SAVE_PATHS = {
    "local": Path("dac_offshore/results"),
    "euler": Path("/cluster/scratch/jwiegner/AdOpT_DAC-Offshore/results"),
}
