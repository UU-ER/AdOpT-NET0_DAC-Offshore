"""
Checks the storage and flow penalties of the emission target runs. Run concat_summaries.py
and extract_run_metrics.py first.
- penalty in objective: solver objective (ub) - total_npv
- storage penalty: 0.1 EUR/MWh x electricity storage throughput (charge + discharge)
- circulation: sum over hours of min(flow i->j, flow j->i), i.e. what the bidirectional flow
  penalty should remove (it is always 0 in that formulation, see modelhub._set_penalized_cost_objective)
"""
from pathlib import Path

import pandas as pd

here = Path(__file__).parent
data_dir = here / "data"

STORAGE_PENALTY_COST = 0.1  # EUR/MWh, default in modelhub

summary = pd.read_csv(data_dir / "Summary_2040_processed.csv")
metrics = pd.read_csv(data_dir / "run_metrics.csv")
runs = summary[["case", "dac_configuration", "emission_target", "climate_year", "total_npv", "ub",
                "emissions_neg"]].merge(
    metrics[["case", "storage_throughput", "flow_co2", "circulation_co2",
             "flow_electricity", "circulation_electricity"]], on="case")

runs["penalty_in_objective"] = runs["ub"] - runs["total_npv"]
runs["storage_penalty"] = STORAGE_PENALTY_COST * runs["storage_throughput"]
runs["other_penalty"] = runs["penalty_in_objective"] - runs["storage_penalty"]
runs["penalty_per_t"] = runs["penalty_in_objective"] / runs["emissions_neg"].where(runs["emissions_neg"] > 0)
runs["circulation_share_co2"] = runs["circulation_co2"] / runs["flow_co2"].where(runs["flow_co2"] > 0)
runs["circulation_share_electricity"] = runs["circulation_electricity"] / runs["flow_electricity"]

runs = runs.sort_values(["climate_year", "dac_configuration", "emissions_neg"])
runs.to_csv(data_dir / "penalty_check.csv", index=False)
print(f"Saved {data_dir / 'penalty_check.csv'}")

columns = ["climate_year", "dac_configuration", "emission_target", "penalty_in_objective", "storage_penalty",
           "other_penalty", "penalty_per_t", "circulation_co2", "circulation_share_co2",
           "circulation_electricity", "circulation_share_electricity"]
print(runs[columns].to_string(index=False, float_format=lambda x: f"{x:,.3g}"))
