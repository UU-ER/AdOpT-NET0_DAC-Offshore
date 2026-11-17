import argparse
import itertools

import adopt_net0 as adopt
from dac_offshore.create_input_data import InputDataCreator
from dac_offshore.model_api import ModelApi
from dac_offshore.global_vars import *

TASKS = list(itertools.product(BASELINE_SCENARIO, CLIMATE_YEARS))

# Time aggregation settings, applied on top of ConfigModel.json (input data stays untouched)
TYPICAL_DAYS = 20
TD_METHOD = 1  # 1: everything clustered, 2: balances + technologies_with_full_res at full resolution
TECHNOLOGIES_WITH_FULL_RES = None  # None: keep list from ConfigModel.json
EXTREME_PERIODS = True  # add extreme days (peak demand, lowest wind, PV, generic production, hydro inflow) as extra typical days


def apply_typical_days(config, n_days, method, full_res_technologies=None, extreme_periods=False):
    td_config = config["optimization"]["typicaldays"]
    td_config["N"]["value"] = n_days
    td_config["method"]["value"] = method
    td_config["extreme_periods"] = {"value": extreme_periods}
    if full_res_technologies is not None:
        td_config["technologies_with_full_res"]["value"] = full_res_technologies


def build_model_reduced_ts(m_api, n_days, method, full_res_technologies=None, extreme_periods=False):
    # Same as ModelApi.build_model, but the typical-day settings are patched in right after
    # ConfigModel.json is read, since clustering happens inside DataHandle.read_data()
    m_api.model = adopt.ModelHub()
    data = m_api.model.data
    read_model_config = data._read_model_config

    def read_model_config_patched():
        read_model_config()
        apply_typical_days(data.model_config, n_days, method, full_res_technologies, extreme_periods)

    data._read_model_config = read_model_config_patched
    m_api.model.read_data(m_api.input_data_path, start_period=m_api.start_period, end_period=m_api.end_period)
    InputDataCreator.define_charging_efficiencies(m_api.model)


def main(task_id, run_on, n_days, method, extreme_periods):
    # Baseline emissions
    scenario, cy = TASKS[task_id]
    # separate run id and emissions file, so that full-resolution results are not overwritten
    td_tag = f"TD{n_days}_M{method}" + ("_E" if extreme_periods else "")
    m_api = ModelApi(test=TEST, run_id=f"{RUN_ID}_{td_tag}", climate_year=cy, scenario=scenario)
    m_api.baseline_emissions_path = m_api.baseline_emissions_path.with_name(
        f"{m_api.baseline_emissions_path.stem}_{td_tag}.json"
    )
    build_model_reduced_ts(m_api, n_days, method, TECHNOLOGIES_WITH_FULL_RES, extreme_periods)
    m_api.define_save_paths(SAVE_PATHS[run_on])
    m_api.construct_model()
    m_api.solve_model(optimization_type="cost")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_id", type=int, default=None, help="default: all")
    parser.add_argument("--run_on", type=str, default="local", choices=["local", "euler"])
    parser.add_argument("--typical_days", type=int, default=TYPICAL_DAYS)
    parser.add_argument("--method", type=int, default=TD_METHOD, choices=[1, 2])
    parser.add_argument("--extreme_periods", action=argparse.BooleanOptionalAction, default=EXTREME_PERIODS)
    args = parser.parse_args()

    task_ids = range(len(TASKS)) if args.task_id is None else [args.task_id]
    for task_id in task_ids:
        main(task_id, args.run_on, args.typical_days, args.method, args.extreme_periods)
