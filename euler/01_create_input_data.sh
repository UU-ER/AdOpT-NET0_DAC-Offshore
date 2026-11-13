#!/bin/bash
# Creates the input data, from the repository folder:
#   sbatch euler/01_create_input_data.sh
#SBATCH --job-name=dac_create_input
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=16G
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err

module load stack/2024-06
module load gcc/12.2.0
module load python/3.12.8
module load gurobi/13.0.0

source /cluster/home/jwiegner/AdOpT_DAC-Offshore/.venv/bin/activate
cd /cluster/home/jwiegner/AdOpT_DAC-Offshore

python main_dac_offshore_create_input_data.py
