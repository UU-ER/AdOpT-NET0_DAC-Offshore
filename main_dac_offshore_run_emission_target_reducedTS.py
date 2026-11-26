"""
Emission-target runs (as main_dac_offshore_run_emission_target.py) with typical days.

The typical days are the same as in the No_DAC baseline of
main_dac_offshore_run_baseline_emissions_reducedTS.py (same settings and run id), and
the positive-emission limit is the baseline emissions of that run:

- The DAC input data is the No_DAC input data plus DAC, heat pumps, CO2 storage and
  the CO2 pipeline, with the same time series. The clustering is therefore done on the
  series of the baseline only, exactly as in the baseline run.
- The series of the added technologies (e.g. DAC and heat pump performance) are
  represented by the same days: the medoid of each typical day, or the extreme day.
  They are not rescaled, so that the coefficients of one technology stay consistent
  with each other (they all come from the same real hour).
- If the baseline results are found, the day sequence is checked against them.
"""
import argparse
import itertools
import json
import logging
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

import adopt_net0.data_management.handle_input_data as handle_input_data
from adopt_net0.data_management.handle_input_data import DataHandle
from dac_offshore.model_api import ModelApi
from dac_offshore.global_vars import *
from main_dac_offshore_run_baseline_emissions_reducedTS import (
    EXTREME_PERIODS,
    TD_METHOD,
    TECHNOLOGIES_WITH_FULL_RES,
    TYPICAL_DAYS,
    build_model_reduced_ts,
    td_tag,
)

log = logging.getLogger(__name__)

TASKS = list(itertools.product(NEGATIVE_EMMISSIONS_MT, DAC_SCENARIOS, CLIMATE_YEARS))

TimeSeriesAggregation = handle_input_data.tsam.TimeSeriesAggregation


def baseline_technologies(input_data_path):
    """(node, technology) of the baseline input data, named as in DataHandle"""
    technologies = set()
    for path in Path(input_data_path).glob("period*/node_data/*/Technologies.json"):
        node = path.parent.name
        at_node = json.loads(path.read_text())
        technologies.update((node, technology) for technology in at_node["new"])
        technologies.update((node, f"{technology}_existing") for technology in at_node["existing"])
    return technologies


class BaselineDaysAggregation:
    """
    Stands in for tsam.TimeSeriesAggregation in DataHandle._cluster_data. Clusters the
    series of the baseline technologies as in the baseline run, and takes the series of
    the added technologies on the same days.
    """

    def __init__(self, time_series, base_technologies, weightDict=None, **kwargs):
        columns = time_series.columns.to_frame(index=False)
        is_added = (columns["type_series"] == "tec_series") & ~pd.Series(
            list(zip(columns["Node"], columns["Key1"]))
        ).isin(base_technologies)
        self.columns = time_series.columns
        self.added = self._subset(time_series, is_added.values)
        self.hours_per_period = kwargs["hoursPerPeriod"]
        base = self._subset(time_series, ~is_added.values)

        # the baseline weights only depend on the baseline series (grouped weighting
        # counts the series per group), the extreme-period helper columns are the same
        weights = {c: w for c, w in (weightDict or {}).items() if c[0] == "extreme_periods"}
        if weightDict and len(weights) < len(weightDict):
            is_helper = base.columns.get_level_values("type_series") == "extreme_periods"
            weights.update(DataHandle._grouped_clustering_weights(base.loc[:, ~is_helper]))
        self.base = TimeSeriesAggregation(base, weightDict=weights if weights else None, **kwargs)
        log.info(f"Typical days from {base.shape[1]} baseline series, "
                 f"{self.added.shape[1]} series of added technologies on the same days")

    @staticmethod
    def _subset(time_series, columns):
        # new column index, so that its levels are built as for the baseline matrix
        # (tsam fails if the level order and the sorted column order differ)
        subset = time_series.loc[:, columns]
        subset.columns = pd.MultiIndex.from_tuples(subset.columns, names=time_series.columns.names)
        return subset

    def __getattr__(self, name):
        # _clusterOrder, _clusterPeriodNoOccur, extremePeriods, ...
        return getattr(self.base, name)

    def createTypicalPeriods(self):
        typical_periods = self.base.createTypicalPeriods()
        if self.added.empty:
            return typical_periods

        # real day of each typical day: medoids, then the appended extreme days
        cluster_order = np.asarray(self.base._clusterOrder)
        center_indices = list(self.base.clusterCenterIndices) + [
            period["stepNo"] for period in getattr(self.base, "extremePeriods", {}).values()
        ]
        if len(center_indices) != len(self.base._clusterPeriodNoOccur) or any(
            cluster_order[day] != cluster for cluster, day in enumerate(center_indices)
        ):
            raise ValueError("Typical days are not real days of their own cluster, use "
                             "medoidRepresentation and extreme_period_method append")

        added = TimeSeriesAggregation(
            self.added,
            noTypicalPeriods=len(center_indices),
            hoursPerPeriod=self.hours_per_period,
            predefClusterOrder=cluster_order,
            predefClusterCenterIndices=center_indices,
            rescaleClusterPeriods=False,
        )
        typical_added = added.createTypicalPeriods()
        typical_added.index = typical_periods.index
        return pd.concat([typical_periods, typical_added], axis=1).reindex(columns=self.columns)


def build_model_baseline_days(m_api, base_technologies, n_days, method, extreme_periods):
    def aggregation(time_series, **kwargs):
        return BaselineDaysAggregation(time_series, base_technologies, **kwargs)

    handle_input_data.tsam.TimeSeriesAggregation = aggregation
    try:
        build_model_reduced_ts(m_api, n_days, method, TECHNOLOGIES_WITH_FULL_RES, extreme_periods)
    finally:
        handle_input_data.tsam.TimeSeriesAggregation = TimeSeriesAggregation


def check_baseline_sequence(m_api, baseline_root):
    """Compares the day sequence with the baseline run (latest run in baseline_root)"""
    runs = sorted((baseline_root / str(m_api.climate_year) / BASELINE_SCENARIO[0]).glob(
        "*_baseline_*/optimization_results.h5"))
    if not runs:
        log.warning(f"No baseline results in {baseline_root}, typical days not checked")
        print(f"WARNING: no baseline results in {baseline_root}, typical days not checked")
        return
    with h5py.File(runs[-1], "r") as f:
        sequence = f["k_means_specs/period1/sequence"][:]
    if not np.array_equal(sequence, m_api.model.data.k_means_specs["period1"]["sequence"]):
        raise ValueError(f"Typical days differ from the baseline run {runs[-1].parent}")
    log.info(f"Typical days are the same as in {runs[-1].parent}")


def main(task_id, run_on, n_days, method, extreme_periods, baseline_results):
    # Emission reduction
    neg_target_Mt, scenario, cy = TASKS[task_id]
    # same run id and baseline emissions file as the baseline with typical days
    tag = td_tag(n_days, method, extreme_periods)
    run_id = f"{RUN_ID}_{tag}"
    m_api = ModelApi(test=TEST, run_id=run_id, climate_year=cy, scenario=scenario)
    m_api.baseline_emissions_path = m_api.baseline_emissions_path.with_name(
        f"{m_api.baseline_emissions_path.stem}_{tag}.json"
    )
    if not m_api.baseline_emissions_path.exists():
        raise FileNotFoundError(f"{m_api.baseline_emissions_path} not found, run "
                                "main_dac_offshore_run_baseline_emissions_reducedTS.py first")

    m_baseline = ModelApi(test=TEST, run_id=run_id, climate_year=cy, scenario=BASELINE_SCENARIO[0])
    build_model_baseline_days(m_api, baseline_technologies(m_baseline.input_data_path),
                              n_days, method, extreme_periods)
    baseline_root = Path(baseline_results) if baseline_results else SAVE_PATHS[run_on] / (
        f"2040_test_{run_id}" if TEST else f"2040_{run_id}")
    check_baseline_sequence(m_api, baseline_root)

    m_api.define_save_paths(SAVE_PATHS[run_on])
    m_api.construct_model()
    m_api.solve_model(optimization_type="cost_at_emission_reduction", neg_target_Mt=neg_target_Mt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_id", type=int, default=None, help="default: all")
    parser.add_argument("--run_on", type=str, default="local", choices=["local", "euler"])
    # must be the same as for the baseline run
    parser.add_argument("--typical_days", type=int, default=TYPICAL_DAYS)
    parser.add_argument("--method", type=int, default=TD_METHOD, choices=[1, 2])
    parser.add_argument("--extreme_periods", action=argparse.BooleanOptionalAction, default=EXTREME_PERIODS)
    parser.add_argument("--baseline_results", type=str, default=None,
                        help="folder 2040_<run id> of the baseline run, default: in the save path")
    args = parser.parse_args()

    task_ids = range(len(TASKS)) if args.task_id is None else [args.task_id]
    for task_id in task_ids:
        main(task_id, args.run_on, args.typical_days, args.method, args.extreme_periods,
             args.baseline_results)
