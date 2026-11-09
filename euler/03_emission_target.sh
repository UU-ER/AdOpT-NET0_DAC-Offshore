#!/bin/bash
# Cost at emission target, one array task per negative fraction x DAC scenario x climate year,
# from the repository folder:
#   sbatch euler/03_emission_target.sh
#   sbatch --dependency=afterok:<job id of 02> euler/03_emission_target.sh
# Number of tasks: see TASKS in main_dac_offshore_run_emission_target.py
#SBATCH --job-name=dac_emission_target
#SBATCH --array=0-35
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

source /cluster/home/jwiegner/AdOpT_DAC-Offshore/.venv/bin/activate
cd /cluster/home/jwiegner/AdOpT_DAC-Offshore

python main_dac_offshore_run_emission_target.py --task_id ${SLURM_ARRAY_TASK_ID} --run_on euler
