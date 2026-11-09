#!/bin/bash
# Run the full DAC offshore pipeline, e.g. from the repository folder:
#   sbatch euler/run_dac_offshore.sh
# This job creates the input data and then submits the solves as SLURM arrays:
#   baseline : 1 task per climate year
#   max      : 1 task per climate year, task i starts when baseline task i is done
#   target   : 1 task per fraction x DAC scenario x climate year, starts when all baseline and max tasks are done
# Run every model with one timestep only (test mode) instead of the full year:
#   ONE_TIMESTEP=1 sbatch euler/run_dac_offshore.sh
# Results (h5 files, Summary.xlsx, solver logs, emission data json files) are written to
# RESULTS_DIR (default: /cluster/scratch/jwiegner/AdOpT_DAC-Offshore), e.g.
#   RESULTS_DIR=/cluster/scratch/jwiegner/dac_run2 sbatch euler/run_dac_offshore.sh
# A single stage can also be run by hand, e.g.
#   sbatch --array=0-2 --cpus-per-task=16 euler/run_dac_offshore.sh baseline
# The number of tasks of a stage is printed by: python euler/run_task.py count <stage>
#SBATCH --job-name=dac_create
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=16G
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --error=logs/%x_%A_%a.err

STAGE=${1:-create}
RESULTS_DIR=${RESULTS_DIR:-/cluster/scratch/jwiegner/AdOpT_DAC-Offshore}   # all results go here
ONE_TIMESTEP=${ONE_TIMESTEP:-0}         # 1: one timestep (test=True), 0: full year (test=False)
SOLVE_TIME=${SOLVE_TIME:-24:00:00}
SOLVE_CPUS=${SOLVE_CPUS:-16}            # Gurobi threads in ConfigModel.json
SOLVE_MEM_PER_CPU=${SOLVE_MEM_PER_CPU:-4G}

module load stack/2024-06
module load gcc/12.2.0
module load python/3.12.8
module load gurobi/13.0.0

source /cluster/home/jwiegner/AdOpT_DAC-Offshore/.venv/bin/activate
cd /cluster/home/jwiegner/AdOpT_DAC-Offshore

if [ "${STAGE}" != "create" ]; then
    python euler/run_task.py run ${STAGE} ${SLURM_ARRAY_TASK_ID} --one_timestep ${ONE_TIMESTEP} \
        --results_dir ${RESULTS_DIR}
    exit $?
fi

python euler/run_task.py run create 0 || exit 1

submit() {
    STAGE_NAME=$1; shift
    N_TASKS=$(python euler/run_task.py count ${STAGE_NAME})
    sbatch --parsable \
        --job-name=dac_${STAGE_NAME} \
        --array=0-$((N_TASKS - 1)) \
        --time=${SOLVE_TIME} \
        --cpus-per-task=${SOLVE_CPUS} \
        --mem-per-cpu=${SOLVE_MEM_PER_CPU} \
        --kill-on-invalid-dep=yes \
        --export=ALL,ONE_TIMESTEP=${ONE_TIMESTEP},RESULTS_DIR=${RESULTS_DIR} \
        "$@" euler/run_dac_offshore.sh ${STAGE_NAME}
}

JOB_BASELINE=$(submit baseline)
JOB_MAX=$(submit max --dependency=aftercorr:${JOB_BASELINE})
JOB_TARGET=$(submit target --dependency=afterok:${JOB_BASELINE}:${JOB_MAX})

echo "Submitted baseline ${JOB_BASELINE}, max ${JOB_MAX}, target ${JOB_TARGET}"
