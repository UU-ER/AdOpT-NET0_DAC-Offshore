"""
Runs one slice of a main_dac_offshore_*.py script as a Slurm array task.

The main scripts are executed unchanged. Before they run, the loop lists in
dac_offshore.global_vars are narrowed to the single combination belonging to
this array task, so the script's own loops run exactly once.

Parallel tasks share result files that are written read-modify-write
(dac_offshore/emission_data/*.json and Summary.xlsx). To keep them consistent,
everything in ModelApi.solve_model runs under a cross-node lock, except the
solver call itself, which runs unlocked.

With --one_timestep 1 every ModelApi is created with test=True (one timestep,
periods 50-51, test result paths); with --one_timestep 0 with test=False (full
year). Without the option, the test value hard-coded in the script is used.

With --results_dir DIR the solve stages write everything to DIR instead of the
repository: results to DIR/dac_offshore/results and the emission data json files
to DIR/dac_offshore/emission_data (copied from the repository on first use).

Usage:
    python euler/run_task.py count <stage>                                    # number of array tasks
    python euler/run_task.py run <stage> <task_id> [--one_timestep 0|1] [--results_dir DIR]
with <stage> in: create, baseline, max, target
"""
import argparse
import itertools
import os
import random
import runpy
import shutil
import socket
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))
os.chdir(REPO_DIR)

import dac_offshore.global_vars as gv

SCRIPTS = {
    "create": "main_dac_offshore_create_input_data.py",
    "baseline": "main_dac_offshore_run_baseline_emissions.py",
    "max": "main_dac_offshore_run_max_emission_reduction.py",
    "target": "main_dac_offshore_run_emission_target.py",
}


def task_combinations(stage):
    """Returns the list of global_vars overrides, one per array task."""
    if stage == "create":
        return [{}]
    if stage in ("baseline", "max"):
        return [{"CLIMATE_YEARS": [cy]} for cy in gv.CLIMATE_YEARS]
    if stage == "target":
        return [
            {"NEGATIVE_FRACTIONS": [nf], "DAC_SCENARIOS": [sc], "CLIMATE_YEARS": [cy]}
            for nf, sc, cy in itertools.product(
                gv.NEGATIVE_FRACTIONS, gv.DAC_SCENARIOS, gv.CLIMATE_YEARS
            )
        ]
    raise ValueError(f"Unknown stage {stage}")


class DirLock:
    """Mutex based on atomic mkdir, which works across nodes on shared file systems."""

    def __init__(self, path, stale_after=1800, poll=2):
        self.path = Path(path)
        self.stale_after = stale_after
        self.poll = poll
        self.held = False

    def acquire(self):
        while True:
            try:
                os.mkdir(self.path)
                (self.path / "owner").write_text(
                    f"{socket.gethostname()} pid={os.getpid()} "
                    f"job={os.environ.get('SLURM_JOB_ID')}_{os.environ.get('SLURM_ARRAY_TASK_ID')}\n"
                )
                self.held = True
                return
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > self.stale_after:
                        print(f"Removing stale lock {self.path}", flush=True)
                        shutil.rmtree(self.path, ignore_errors=True)
                        continue
                except FileNotFoundError:
                    continue
                time.sleep(self.poll + random.random())

    def release(self):
        if self.held:
            shutil.rmtree(self.path, ignore_errors=True)
            self.held = False


def install_result_file_lock(lock_path):
    import adopt_net0 as adopt
    from dac_offshore.model_api import ModelApi

    lock = DirLock(lock_path)

    orig_solve_model = ModelApi.solve_model

    def solve_model(self, *args, **kwargs):
        lock.acquire()
        try:
            return orig_solve_model(self, *args, **kwargs)
        finally:
            lock.release()

    ModelApi.solve_model = solve_model

    orig_define_solver_settings = adopt.ModelHub._define_solver_settings

    def _define_solver_settings(self):
        orig_define_solver_settings(self)
        solver_solve = self.solver.solve

        def solve(*args, **kwargs):
            lock.release()
            try:
                return solver_solve(*args, **kwargs)
            finally:
                lock.acquire()

        self.solver.solve = solve

    adopt.ModelHub._define_solver_settings = _define_solver_settings
    return lock


def patch_model_api(test, emission_data_dir):
    """Sets the test flag (if not None) and the emission data folder of every ModelApi."""
    from dac_offshore.model_api import ModelApi

    orig_init = ModelApi.__init__

    def __init__(self, *args, **kwargs):
        if test is not None:
            if args:
                args = (test,) + args[1:]
            else:
                kwargs["test"] = test
        orig_init(self, *args, **kwargs)
        if emission_data_dir is not None:
            self.baseline_emissions_path = emission_data_dir / self.baseline_emissions_path.name
            self.max_negative_emissions_path = emission_data_dir / self.max_negative_emissions_path.name

    ModelApi.__init__ = __init__


def seed_emission_data(emission_data_dir):
    """Copies the emission data files from the repository if they do not exist yet."""
    emission_data_dir.mkdir(parents=True, exist_ok=True)
    for source in (REPO_DIR / "dac_offshore" / "emission_data").glob("*.json"):
        target = emission_data_dir / source.name
        if not target.exists():
            tmp = target.with_suffix(f".json.tmp{os.getpid()}")
            shutil.copy(source, tmp)
            os.replace(tmp, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["count", "run"])
    parser.add_argument("stage", choices=list(SCRIPTS))
    parser.add_argument("task_id", type=int, nargs="?", default=0)
    parser.add_argument("--one_timestep", type=int, choices=[0, 1], default=None)
    parser.add_argument("--results_dir", type=Path, default=None)
    args = parser.parse_args()

    stage = args.stage
    combinations = task_combinations(stage)

    if args.mode == "count":
        print(len(combinations))
        return

    task_id = args.task_id
    overrides = combinations[task_id]
    for name, value in overrides.items():
        setattr(gv, name, value)
    print(
        f"Stage {stage}, task {task_id}/{len(combinations) - 1}: {overrides}, "
        f"one_timestep={args.one_timestep}, results_dir={args.results_dir}",
        flush=True,
    )

    if stage != "create":
        if args.results_dir is not None:
            results_dir = args.results_dir.resolve()
            emission_data_dir = results_dir / "dac_offshore" / "emission_data"
        else:
            results_dir = REPO_DIR
            emission_data_dir = None
        lock = install_result_file_lock(
            (emission_data_dir or REPO_DIR / "dac_offshore" / "emission_data") / ".results.lock"
        )
        patch_model_api(
            None if args.one_timestep is None else bool(args.one_timestep),
            emission_data_dir,
        )
        if emission_data_dir is not None:
            lock.acquire()
            try:
                seed_emission_data(emission_data_dir)
            finally:
                lock.release()
        # The scripts save to the relative path dac_offshore/results
        os.chdir(results_dir)

    runpy.run_path(str(REPO_DIR / SCRIPTS[stage]), run_name="__main__")


if __name__ == "__main__":
    main()
