"""One evolutionary engine; every method and ablation is a Config that flips switches."""
import time
from dataclasses import dataclass

import numpy as np

from steel.encoding import TOL, evaluate
from steel.model import solve
from steel.qkernel import median_gamma, rbf_kernel, zz_kernel
from steel.repair import ALL, repair
from steel.surrogate import KRR, RBF_GRID, ZZ_GRID, features, select

MIN_ARCHIVE, MAX_ARCHIVE = 20, 200
RESELECT = 10   # LOO selection of (bandwidth, lam) at KRR fits 1, 11, 21, ...
LP_MODES = ("none", "flat", "polish")


@dataclass(frozen=True)
class Config:
    pop: int = 40
    pm: float = 0.1
    sigma: float = 0.1
    ls_steps: int = 5
    keep: float = 0.5
    rho: float = 10.0
    constraint: str = "deb"        # deb | penalty
    local_search: bool = True
    rules: frozenset = frozenset()
    surrogate: str = "none"        # none | zz | rbf | random
    lp: str = "none"               # none | flat (B3) | polish

    def __post_init__(self):
        if self.lp not in LP_MODES:
            raise ValueError(f"lp must be one of {LP_MODES}, got {self.lp!r}")


METHODS = {
    "B1": Config(constraint="penalty", local_search=False),
    "B2": Config(),
    "B3": Config(lp="flat", local_search=False),
    "Q": Config(rules=ALL, surrogate="zz", lp="polish"),
    "Q-K": Config(rules=ALL, lp="polish"),
    "Q-R": Config(surrogate="zz", lp="polish"),
    "Q-RBF": Config(rules=ALL, surrogate="rbf", lp="polish"),
    "Q-RND": Config(rules=ALL, surrogate="random", lp="polish"),
    **{f"Q-R{i}": Config(rules=ALL - {f"R{i}"}, surrogate="zz", lp="polish") for i in range(1, 9)},
    "Q-NOLP": Config(rules=ALL, surrogate="zz"),   # Q without LP completion (ablation)
}


def lp_complete(prob, z, mode, memo=None):
    """Individual (cost, viol, z) for a fixed z. flat/polish: exact LP on the continuous part for y = z[:ny].
    Infeasible LP: flat gives (inf, 1.0, z) (such parents tie); polish keeps z with its own graded evaluate().
    memo (one dict per run): the LP outcome depends only on y, so a repeated y reuses it instead of re-solving."""
    if mode != "none":
        k = z[:prob.ny].tobytes()
        if memo is None or k not in memo:
            sol = solve(prob, fixed_y=z[:prob.ny])
            hit = (*evaluate(prob, sol.z)[::2], sol.z) if sol.ok else None
            if memo is None:
                memo = {}
            memo[k] = hit
        hit = memo[k]
        if hit is not None:
            cost, viol, lz = hit
            return cost, viol, lz.copy()
        if mode == "flat":
            return np.inf, 1.0, z
    cost, _, viol = evaluate(prob, z)
    return cost, viol, z


def run(inp, prob, cfg, budget, seed):
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    ny, n = prob.ny, prob.c.size
    span = prob.zub - prob.zlb
    cscale = float(np.abs(prob.c) @ prob.zub + abs(prob.const)) or 1.0
    kernel = {"zz": zz_kernel, "rbf": rbf_kernel}.get(cfg.surrogate)   # rbf gamma is set at each fit
    arch_x, arch_f, history = [], [], []
    state = {"evals": 0, "best": None, "fits": 0, "hp": None}
    memo = {}   # y bytes -> LP outcome; every lookup still counts one evaluation

    def key(ind):
        cost, viol, _ = ind
        if cfg.constraint == "penalty":
            return (0, cost / cscale + cfg.rho * viol)
        return (0, cost) if viol <= TOL else (1, viol)

    def fix(z):
        z = np.clip(z, prob.zlb, prob.zub)
        z[:ny] = np.round(z[:ny])
        return repair(inp, prob, z, cfg.rules) if cfg.rules else z

    def score(z):
        state["evals"] += 1
        ind = lp_complete(prob, z, cfg.lp, memo)
        b = state["best"]
        if b is None or (ind[1] <= TOL and (b[1] > TOL or ind[0] < b[0])) or (b[1] > TOL and ind[1] < b[1]):
            state["best"] = ind
        b = state["best"]
        history.append((state["evals"], b[0] if b[1] <= TOL else np.nan))
        if kernel is not None and np.isfinite(ind[0]):
            arch_x.append(features(inp, prob, ind[2]))
            arch_f.append(ind[0] / cscale + cfg.rho * ind[1])
        return ind

    def prescreen(kids):
        m = max(1, int(cfg.keep * len(kids)))
        if cfg.surrogate == "random":
            return [kids[i] for i in rng.choice(len(kids), m, replace=False)]
        if kernel is None or len(arch_f) < MIN_ARCHIVE:
            return kids
        X, y = np.array(arch_x[-MAX_ARCHIVE:]), np.array(arch_f[-MAX_ARCHIVE:])
        if cfg.surrogate == "rbf":   # gamma = g * median heuristic on this training archive
            mg, grid = median_gamma(X), RBF_GRID
            make = lambda g: lambda P, Q=None: rbf_kernel(P, Q, g * mg)  # noqa: E731
        else:
            grid = ZZ_GRID
            make = lambda w: lambda P, Q=None: zz_kernel(P, Q, a=w)  # noqa: E731
        if state["fits"] % RESELECT == 0:   # D2: LOO selection at fits 1, 11, 21, ...
            state["hp"] = select(lambda w: make(w)(X), grid, y)
        state["fits"] += 1
        w, lam = state["hp"]
        model = KRR(make(w), lam).fit(X, y)
        pred = model.predict(np.array([features(inp, prob, z) for z in kids]))
        return [kids[i] for i in np.argsort(pred)[:m]]

    def random_z():
        z = prob.zlb + rng.random(n) * span
        z[:ny] = rng.random(ny) < 0.3
        return fix(z)

    pop = [score(random_z()) for _ in range(min(cfg.pop, budget))]

    def pick():
        i, j = rng.integers(len(pop), size=2)
        return pop[i] if key(pop[i]) < key(pop[j]) else pop[j]

    while state["evals"] < budget:
        kids = []
        for _ in range(cfg.pop):
            a, b = pick()[2], pick()[2]
            z = np.where(rng.random(n) < 0.5, a, b)
            w = rng.random()
            z[ny:] = w * a[ny:] + (1 - w) * b[ny:]
            flip = rng.random(ny) < cfg.pm
            z[:ny] = np.where(flip, 1 - z[:ny], z[:ny])
            mut = rng.random(n - ny) < cfg.pm
            z[ny:] += mut * rng.normal(0, cfg.sigma, n - ny) * span[ny:]
            kids.append(fix(z))
        scored = []
        for z in prescreen(kids):
            if state["evals"] >= budget:
                break
            scored.append(score(z))
        pop = sorted(pop + scored, key=key)[: cfg.pop]
        if cfg.local_search:
            for _ in range(cfg.ls_steps):
                if state["evals"] >= budget:
                    break
                z = pop[0][2].copy()
                j = rng.integers(ny, n)
                z[j] += rng.normal(0, cfg.sigma / 2) * span[j]
                cand = score(fix(z))
                if key(cand) < key(pop[0]):
                    pop[0] = cand

    cost, viol, z = state["best"]
    return {"cost": float(cost), "viol": float(viol), "feasible": bool(viol <= TOL),
            "evals": state["evals"], "seconds": time.perf_counter() - t0, "history": history, "z": z}
