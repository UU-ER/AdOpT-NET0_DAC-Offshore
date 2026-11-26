#!/bin/bash
# Baseline emissions with typical days, one array task per climate year, from the repository folder:
#   sbatch euler/01_baseline_tsaggregation.sh <number of typical days>
#   e.g. sbatch euler/01_baseline_tsaggregation.sh 20
# Results go to 2040_<run id>_M1_Extreme_<number of typical days>, the baseline emissions to
# baseline_emissions_test_<test>_cy<climate year>_M1_Extreme_<number of typical days>.json
# Number of tasks: see TASKS in main_dac_offshore_run_baseline_emissions_reducedTS.py
#SBATCH --job-name=dac_baseline_tsa
#SBATCH --array=0-2
#SBATCH --time=3:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem-per-cpu=8G
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --error=logs/%x_%A_%a.err

TYPICAL_DAYS=${1:?usage: sbatch euler/01_baseline_tsaggregation.sh <number of typical days>}

module load stack/2024-06
module load gcc/12.2.0
module load python/3.12.8
module load gurobi/13.0.0

source /cluster/home/jwiegner/AdOpT-NET0_DAC-Offshore/.venv/bin/activate
cd /cluster/home/jwiegner/AdOpT-NET0_DAC-Offshore

python main_dac_offshore_run_baseline_emissions_reducedTS.py --task_id ${SLURM_ARRAY_TASK_ID} --run_on euler --typical_days ${TYPICAL_DAYS} || exit 1
