#!/bin/bash
# Cost at emission target with typical days, one array task per negative emission target x DAC scenario
# x climate year, from the repository folder:
#   sbatch euler/03_emission_target_tsaggregation.sh
#   sbatch --dependency=afterok:<job id of 01_baseline_tsaggregation> euler/03_emission_target_tsaggregation.sh
# Needs the baseline emissions of 01_baseline_tsaggregation.sh with the same typical-day settings.
# Number of tasks: see TASKS in main_dac_offshore_run_emission_target_reducedTS.py
#SBATCH --job-name=dac_emission_target_tsa
#SBATCH --array=0-35
#SBATCH --time=16:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem-per-cpu=16G
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --error=logs/%x_%A_%a.err

module load stack/2024-06
module load gcc/12.2.0
module load python/3.12.8
module load gurobi/13.0.0

source /cluster/home/jwiegner/AdOpT-NET0_DAC-Offshore/.venv/bin/activate
cd /cluster/home/jwiegner/AdOpT-NET0_DAC-Offshore

python main_dac_offshore_run_emission_target_reducedTS.py --task_id ${SLURM_ARRAY_TASK_ID} --run_on euler
