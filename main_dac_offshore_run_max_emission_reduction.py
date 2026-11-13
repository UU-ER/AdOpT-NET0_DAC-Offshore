import argparse
import itertools

from dac_offshore.model_api import ModelApi
from dac_offshore.global_vars import *

TASKS = list(itertools.product(DAC_ALL, CLIMATE_YEARS))


def main(task_id, run_on):
    # Max emissions
    scenario, cy = TASKS[task_id]
    m_api = ModelApi(test=TEST, run_id=RUN_ID, climate_year=cy, scenario=scenario)
    m_api.build_model()
    m_api.define_save_paths(SAVE_PATHS[run_on])
    m_api.construct_model()
    m_api.solve_model(optimization_type="negative_emissions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_id", type=int, default=None, help="default: all")
    parser.add_argument("--run_on", type=str, default="local", choices=["local", "euler"])
    args = parser.parse_args()

    task_ids = range(len(TASKS)) if args.task_id is None else [args.task_id]
    for task_id in task_ids:
        main(task_id, args.run_on)
