from pyomo.environ import SolverFactory
from pyomo.opt import SolverResults, SolverStatus, TerminationCondition
from pyomo.repn.plugins.standard_form import LinearStandardFormCompiler

# Gurobi status code -> legacy Pyomo status, as pyomo's gurobi_direct maps them
_GUROBI_STATUS = {
    1: (SolverStatus.aborted, TerminationCondition.error),
    2: (SolverStatus.ok, TerminationCondition.optimal),
    3: (SolverStatus.warning, TerminationCondition.infeasible),
    4: (SolverStatus.warning, TerminationCondition.infeasibleOrUnbounded),
    5: (SolverStatus.warning, TerminationCondition.unbounded),
    6: (SolverStatus.aborted, TerminationCondition.minFunctionValue),
    7: (SolverStatus.aborted, TerminationCondition.maxIterations),
    8: (SolverStatus.aborted, TerminationCondition.maxEvaluations),
    9: (SolverStatus.aborted, TerminationCondition.maxTimeLimit),
    10: (SolverStatus.aborted, TerminationCondition.unknown),
    11: (SolverStatus.aborted, TerminationCondition.error),
    12: (SolverStatus.error, TerminationCondition.error),
    13: (SolverStatus.warning, TerminationCondition.other),
    15: (SolverStatus.aborted, TerminationCondition.other),
}


class GurobiMatrix:
    """
    Gurobi fed with the model as one constraint matrix

    Pyomo's standard-form compiler builds the matrix in one pass and gurobipy takes it
    in one call, several times faster than gurobi_direct, which adds the constraints
    one at a time. Pyomo's newer gurobi_direct (pyomo.contrib.solver) works the same
    way; solve() takes the arguments AdOpT passes to gurobi_direct and returns the
    same legacy results.

    With persistent = True, solving the same Pyomo model again only updates the
    objective and the constraints on the model's top level (where ModelHub's objective
    functions add them) and keeps everything else in Gurobi, including the last basis.
    """

    def __init__(self, options: dict, persistent: bool = False):
        self.options = options
        self.persistent = persistent
        self._solver_model = None
        self._model = None

    def _compile(self, model):
        import gurobipy as gp

        repn = LinearStandardFormCompiler().write(
            model, mixed_form=True, set_sense=None
        )
        if len(repn.objectives) > 1:
            raise ValueError("Gurobi takes one objective, the model has several")
        columns = repn.columns
        # Pyomo before 6.10 can return fixed variables as columns (when other indices
        # of the same variable are free); they keep their value, not their bounds
        bounds = [(v.value, v.value) if v.fixed else v.bounds for v in columns]
        grb = gp.Model()
        x = grb.addMVar(
            len(columns),
            lb=[-gp.GRB.INFINITY if lb is None else lb for lb, _ in bounds],
            ub=[gp.GRB.INFINITY if ub is None else ub for _, ub in bounds],
            obj=repn.c.toarray()[0] if repn.c.shape[0] else 0.0,
            vtype=[
                (
                    gp.GRB.BINARY
                    if v.is_binary()
                    else gp.GRB.INTEGER if v.is_integer() else gp.GRB.CONTINUOUS
                )
                for v in columns
            ],
        )
        # bound type of a row: 0 equality, 1 upper bound, -1 lower bound
        rows = grb.addMConstr(
            repn.A, x, ["=<>"[row.bound_type] for row in repn.rows], repn.rhs
        )
        if repn.c.shape[0]:
            grb.ObjCon = repn.c_offset[0]
            grb.ModelSense = int(repn.objectives[0].sense)
        self._solver_model, self._x, self._columns = grb, x, columns
        self._model = model
        if self.persistent:
            self._index = {id(v): j for j, v in enumerate(columns)}
            self._vars = x.tolist()
            self._top = {}
            for row, handle in zip(repn.rows, rows.tolist()):
                if row.constraint.parent_block() is model:
                    self._top.setdefault(row.constraint, []).append(handle)

    def _update(self, model):
        """Brings objective and top-level constraints up to date; False if a full compile is needed"""
        import gurobipy as gp
        import numpy as np
        from pyomo.core import Constraint, Objective, minimize, value
        from pyomo.repn import generate_standard_repn

        def linear(expr):
            repn = generate_standard_repn(expr, quadratic=False)
            if not repn.is_linear():
                return None
            columns = [self._index.get(id(v)) for v in repn.linear_vars]
            if None in columns:
                return None
            return columns, [value(c) for c in repn.linear_coefs], value(repn.constant)

        grb, x = self._solver_model, self._x
        current = list(
            model.component_data_objects(Constraint, active=True, descend_into=False)
        )
        added = []
        for con in current:
            if con in self._top:
                continue
            terms = linear(con.body)
            if terms is None:
                return False
            added.append((con, terms))
        objectives = list(
            model.component_data_objects(Objective, active=True, descend_into=True)
        )
        if len(objectives) != 1:
            return False
        objective = linear(objectives[0].expr)
        if objective is None:
            return False
        keep = set(current)
        for con in [c for c in self._top if c not in keep]:
            grb.remove(self._top.pop(con))
        for con, (columns, coefs, constant) in added:
            expr = gp.LinExpr(coefs, [self._vars[j] for j in columns]) + constant
            handles = []
            if con.equality:
                handles.append(grb.addLConstr(expr, "=", value(con.upper)))
            else:
                if con.has_lb():
                    handles.append(grb.addLConstr(expr, ">", value(con.lower)))
                if con.has_ub():
                    handles.append(grb.addLConstr(expr, "<", value(con.upper)))
            self._top[con] = handles
        columns, coefs, constant = objective
        c = np.zeros(len(self._columns))
        np.add.at(c, columns, coefs)
        x.Obj = c
        grb.ObjCon = constant
        grb.ModelSense = 1 if objectives[0].sense == minimize else -1
        return True

    def solve(self, model, tee=False, warmstart=False, logfile=None, keepfiles=False):
        """
        Solves the model and loads the solution into it

        :param model: pyomo model
        :param bool tee: show the solver log
        :param bool warmstart: start from the current variable values
        :param str logfile: file to write the solver log to
        :param bool keepfiles: not used, no files are written
        :return: legacy pyomo results
        """
        import gurobipy as gp

        if not (self.persistent and model is self._model and self._update(model)):
            self._compile(model)
        grb, x, columns = self._solver_model, self._x, self._columns
        grb.Params.LogToConsole = int(tee)
        if logfile:
            grb.Params.LogFile = logfile
        for key, value in self.options.items():
            grb.setParam(key, value)
        if warmstart and any(not v.is_continuous() for v in columns):
            x.Start = [
                gp.GRB.UNDEFINED if v.value is None else v.value for v in columns
            ]

        grb.optimize()

        results = SolverResults()
        results.solver.status, results.solver.termination_condition = (
            _GUROBI_STATUS.get(
                grb.Status, (SolverStatus.error, TerminationCondition.error)
            )
        )
        results.solver.wallclock_time = grb.Runtime
        if grb.SolCount > 0:
            for v, value in zip(columns, x.X.tolist()):
                v.set_value(value, skip_validation=True)
            bound = grb.ObjBound if grb.IsMIP else grb.ObjVal
            if grb.ModelSense == 1:
                results.problem.lower_bound, results.problem.upper_bound = (
                    bound,
                    grb.ObjVal,
                )
            else:
                results.problem.lower_bound, results.problem.upper_bound = (
                    grb.ObjVal,
                    bound,
                )
        self._solver_model = grb
        return results


def get_gurobi_parameters(solveroptions: dict, matrix_handover: bool = True):
    """
    Initiates the gurobi solver and defines solver parameters

    Solver "gurobi" gets the model as one matrix (GurobiMatrix) unless
    matrix_handover is False; "gurobi_persistent" keeps pyomo's persistent interface.

    :param dict solveroptions: dict with solver parameters
    :param bool matrix_handover: use GurobiMatrix for solver "gurobi"
    :return: Gurobi Solver
    """
    options = {
        "TimeLimit": solveroptions["timelim"]["value"] * 3600,
        "MIPGap": solveroptions["mipgap"]["value"],
        "MIPFocus": solveroptions["mipfocus"]["value"],
        "Threads": solveroptions["threads"]["value"],
        "NodefileStart": solveroptions["nodefilestart"]["value"],
        "Method": solveroptions["method"]["value"],
        "Heuristics": solveroptions["heuristics"]["value"],
        "Presolve": solveroptions["presolve"]["value"],
        "BranchDir": solveroptions["branchdir"]["value"],
        "LPWarmStart": solveroptions["lpwarmstart"]["value"],
        "IntFeasTol": solveroptions["intfeastol"]["value"],
        "FeasibilityTol": solveroptions["feastol"]["value"],
        "Cuts": solveroptions["cuts"]["value"],
        "NumericFocus": solveroptions["numericfocus"]["value"],
        "Crossover": solveroptions["crossover"]["value"],
        "NodeMethod": solveroptions["nodemethod"]["value"],
    }
    if matrix_handover and solveroptions["solver"]["value"] == "gurobi":
        return GurobiMatrix(options)
    solver = SolverFactory(solveroptions["solver"]["value"], solver_io="python")
    solver.options.update(options)

    return solver


def get_glpk_parameters(solveroptions: dict):
    """
    Initiates the glpk solver and defines solver parameters

    :param dict solveroptions: dict with solver parameters
    :return: Gurobi Solver
    """
    solver = SolverFactory("glpk")

    return solver


def get_set_t(config: dict, model_block):
    """
    Returns the correct set_t for different clustering options

    :param dict config: config dict
    :param model_block: pyomo block holding set_t_full and set_t_clustered
    :return: set_t
    """
    if config["optimization"]["typicaldays"]["N"]["value"] == 0:
        return model_block.set_t_full
    elif config["optimization"]["typicaldays"]["method"]["value"] == 1:
        return model_block.set_t_clustered
    elif config["optimization"]["typicaldays"]["method"]["value"] == 2:
        return model_block.set_t_full


def get_hour_factors(config: dict, data, period: str) -> list:
    """
    Returns the correct hour factors to use for global balances

    :param dict config: config dict
    :param data: DataHandle
    :return: hour factors
    """
    if config["optimization"]["typicaldays"]["N"]["value"] == 0:
        return [1] * len(data.topology["time_index"]["full"])
    elif config["optimization"]["typicaldays"]["method"]["value"] == 1:
        return data.k_means_specs[period]["factors"]
    elif config["optimization"]["typicaldays"]["method"]["value"] == 2:
        return [1] * len(data.topology["time_index"]["full"])


def get_nr_timesteps_averaged(config: dict) -> int:
    """
    Returns the correct number of timesteps averaged

    :param dict config: config dict
    :return: nr_timesteps_averaged
    """
    if config["optimization"]["timestaging"]["value"] != 0:
        nr_timesteps_averaged = config["optimization"]["timestaging"]["value"]
    else:
        nr_timesteps_averaged = 1

    return nr_timesteps_averaged
