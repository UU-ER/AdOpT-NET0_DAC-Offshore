#!/bin/bash
# Baseline emissions and max negative emissions, one array task per climate year, from the repository folder:
#   sbatch euler/02_baseline_and_max_emissions.sh
#   sbatch --dependency=afterok:<job id of 01> euler/02_baseline_and_max_emissions.sh
# Each task runs the baseline and then the max emissions of its climate year
# (max emissions need the baseline emissions of the same climate year).
# Number of tasks: see TASKS in main_dac_offshore_run_baseline_emissions.py
#SBATCH --job-name=dac_baseline_max
#SBATCH --array=0-2
#SBATCH --time=16:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem-per-cpu=8G
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --error=logs/%x_%A_%a.err

module load stack/2024-06
module load gcc/12.2.0
module load python/3.12.8
module load gurobi/13.0.0

source /cluster/home/jwiegner/AdOpT-NET0_DAC-Offshore/.venv/bin/activate
cd /cluster/home/jwiegner/AdOpT-NET0_DAC-Offshore

python main_dac_offshore_run_baseline_emissions.py --task_id ${SLURM_ARRAY_TASK_ID} --run_on euler || exit 1
python main_dac_offshore_run_max_emission_reduction.py --task_id ${SLURM_ARRAY_TASK_ID} --run_on euler
