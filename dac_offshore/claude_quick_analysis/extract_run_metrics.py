"""
Extracts key numbers from the h5 result files listed in the processed summary
(run concat_summaries.py first). Only the datasets needed are read, so this is
much faster than loading the full results.
"""
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from validate_vre_potential.read_data import read_technology_design

here = Path(__file__).parent
SUMMARY_FILE = here / "data" / "Summary_2040_processed.csv"
DESIGN_FILE = here / "data" / "technology_design.csv"
METRICS_FILE = here / "data" / "run_metrics.csv"
NETWORK_DESIGN_FILE = here / "data" / "network_design.csv"
CO2_STORAGE_LIMITS_FILE = here.parent / "clean_data" / "co2_storage_limits" / "CO2_storage_limits_2040.csv"

# Injection rate (t/h) in PermanentStorage_CO2_simple.json, used for nodes not in the limits file
DEFAULT_INJECTION_RATE_MAX = 1500

RE_TECHNOLOGIES = ["Offshore_Wind", "Onshore_Wind", "PV"]
BATTERY_TECHNOLOGIES = ["Storage_Battery_new", "Storage_Battery_Offshore"]


def sum_technology_operation(path_h5, technology_prefix, variable):
    """
    Sums a technology operation variable over all nodes and time steps
    """
    total = 0
    with h5py.File(path_h5, "r") as hdf_file:
        operation = hdf_file["operation/technology_operation/period1"]
        for node in operation:
            for technology in operation[node]:
                if technology.startswith(technology_prefix):
                    total += operation[node][technology][variable][:].sum()
    return total


def sum_energy_balance(path_h5, carrier, variable):
    """
    Sums an energy balance variable of a carrier over all nodes and time steps
    """
    total = 0
    with h5py.File(path_h5, "r") as hdf_file:
        balance = hdf_file["operation/energy_balance/period1"]
        for node in balance:
            if carrier in balance[node]:
                total += balance[node][carrier][variable][:].sum()
    return total


def get_co2_pipeline_flow(path_h5):
    """
    Returns the total absolute flow over all CO2 pipeline arcs (t/yr)
    """
    total = 0
    with h5py.File(path_h5, "r") as hdf_file:
        if "CO2_Pipeline" not in hdf_file["operation/networks/period1"]:
            return 0
        pipelines = hdf_file["operation/networks/period1/CO2_Pipeline"]
        for arc in pipelines:
            total += np.abs(pipelines[arc]["flow"][:]).sum()
    return total


def get_upper_bound_utilisation(path_h5):
    """
    Checks which constraint limits the negative emissions. For each candidate
    the utilisation is given in % (100% = constraint binding):
    - DAC: hourly output relative to max_out (= size x productivity), lowest hour
    - CO2 storage: injected CO2 relative to the max. injection rate and the reservoir size
    - VRE: share of hours without any curtailment (if electricity is curtailed
      in an hour, more VRE would not help in that hour)
    - CO2 transport: highest hourly flow relative to the pipeline size, over all arcs
    """
    co2_storage_limits = pd.read_csv(CO2_STORAGE_LIMITS_FILE, thousands=",")
    co2_storage_limits.columns = co2_storage_limits.columns.str.strip()
    injection_rate_max = co2_storage_limits.set_index("Node")["injection_rate_max"]

    dac_utilisation = []
    injected = 0
    injection_capacity = 0
    storage_level = 0
    storage_size = 0
    curtailment = 0

    with h5py.File(path_h5, "r") as hdf_file:
        operation = hdf_file["operation/technology_operation/period1"]
        design = hdf_file["design/nodes/period1"]
        for node in operation:
            for technology in operation[node]:
                tec_operation = operation[node][technology]
                if technology.startswith("DAC_Adsorption"):
                    output = tec_operation["CO2captured_output"][:]
                    dac_utilisation.append((output / tec_operation["max_out"][:]).min())
                if technology.startswith("PermanentStorage_CO2"):
                    injected += tec_operation["CO2captured_input"][:].sum()
                    injection_capacity += injection_rate_max.get(node, DEFAULT_INJECTION_RATE_MAX) * 8760
                    storage_level += tec_operation["storage_level"][-1]
                    storage_size += design[node][technology]["size"][0]
                if technology in RE_TECHNOLOGIES:
                    curtailment = curtailment + tec_operation["curtailment_electricity"][:]

        pipeline_utilisation = 0
        if "CO2_Pipeline" in hdf_file["design/networks/period1"]:
            pipeline_design = hdf_file["design/networks/period1/CO2_Pipeline"]
            pipeline_operation = hdf_file["operation/networks/period1/CO2_Pipeline"]
            for arc in pipeline_design:
                size = pipeline_design[arc]["size"][()]
                if size > 0:
                    max_flow = np.abs(pipeline_operation[arc]["flow"][:]).max()
                    pipeline_utilisation = max(pipeline_utilisation, max_flow / size)

    utilisation = {
        "util_dac_min_hour": min(dac_utilisation) if dac_utilisation else np.nan,
        "util_co2_injection_rate": injected / injection_capacity if injection_capacity else np.nan,
        "util_co2_storage_volume": storage_level / storage_size if storage_size else np.nan,
        "util_vre_hours_without_curtailment": (np.asarray(curtailment) < 1).mean(),
        "util_co2_pipeline_max_arc": pipeline_utilisation,
        "min_hourly_curtailment": np.min(curtailment),
    }
    return utilisation


def get_run_metrics(path_h5):
    metrics = {}

    # DAC and CO2 storage
    for location in ["onshore", "offshore"]:
        metrics[f"dac_captured_{location}"] = sum_technology_operation(
            path_h5, f"DAC_Adsorption_{location}", "CO2captured_output"
        )
    metrics["co2_stored"] = sum_technology_operation(
        path_h5, "PermanentStorage_CO2", "CO2captured_input"
    )
    metrics["co2_pipeline_flow"] = get_co2_pipeline_flow(path_h5)

    # Electricity (MWh)
    for technology in RE_TECHNOLOGIES:
        metrics[f"generation_{technology}"] = sum_technology_operation(
            path_h5, technology, "electricity_output"
        )
        metrics[f"curtailment_{technology}"] = sum_technology_operation(
            path_h5, technology, "curtailment_electricity"
        )
    metrics["battery_discharge"] = sum(
        sum_technology_operation(path_h5, technology, "electricity_output")
        for technology in BATTERY_TECHNOLOGIES
    )
    metrics["battery_charge"] = sum(
        sum_technology_operation(path_h5, technology, "electricity_input")
        for technology in BATTERY_TECHNOLOGIES
    )
    metrics["dac_electricity"] = sum_technology_operation(
        path_h5, "DAC_Adsorption", "electricity_input"
    )
    metrics["dac_heat"] = sum_technology_operation(path_h5, "DAC_Adsorption", "heat_input")
    metrics["electricity_demand"] = sum_energy_balance(path_h5, "electricity", "demand")
    metrics["network_consumption"] = sum_energy_balance(
        path_h5, "electricity", "network_consumption"
    )

    return metrics


def read_network_design(path_h5):
    """
    Reads the design of all networks: one row per arc with size and annualised costs
    """
    variables = ["size", "capex", "opex_fixed", "opex_variable"]
    rows = []
    with h5py.File(path_h5, "r") as hdf_file:
        networks = hdf_file["design/networks/period1"]
        for network in networks:
            for arc in networks[network]:
                row = {"Network": network, "Arc_ID": arc}
                for variable in variables:
                    row[variable] = np.sum(networks[network][arc][variable][()])
                rows.append(row)
    return pd.DataFrame(rows)


summary = pd.read_csv(SUMMARY_FILE)

designs = []
network_designs = []
metrics = []
for _, run in summary.iterrows():
    path_h5 = Path(run["result_path"]) / "optimization_results.h5"
    if not path_h5.exists():
        print(f"Skipping {run['case']}: no h5 file")
        continue
    print(f"Reading {run['case']}")

    design = read_technology_design(str(path_h5))
    design["case"] = run["case"]
    designs.append(design)

    network_design = read_network_design(path_h5)
    network_design["case"] = run["case"]
    network_designs.append(network_design)

    run_metrics = get_run_metrics(path_h5)
    run_metrics.update(get_upper_bound_utilisation(path_h5))
    run_metrics["case"] = run["case"]
    metrics.append(run_metrics)

design = pd.concat(designs, ignore_index=True)
design = design[design["Variable"] != "technology"]
design["Value"] = pd.to_numeric(design["Value"])
design.to_csv(DESIGN_FILE, index=False)
print(f"Saved {DESIGN_FILE}")

network_design = pd.concat(network_designs, ignore_index=True)
network_design.to_csv(NETWORK_DESIGN_FILE, index=False)
print(f"Saved {NETWORK_DESIGN_FILE}")

metrics = pd.DataFrame(metrics)
metrics = summary[["case", "dac_configuration", "emission_target", "climate_year"]].merge(metrics, on="case")
metrics.to_csv(METRICS_FILE, index=False)
print(f"Saved {METRICS_FILE}")
