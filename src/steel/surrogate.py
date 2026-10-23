"""Kernel ridge surrogate, the 12 design features it sees, and LOO hyperparameter selection (D2)."""
import numpy as np

N_FEATURES = 12
ZZ_GRID = (0.05, 0.1, 0.2, 0.5, 1.0)     # ZZ bandwidth a: x -> a * x before the feature map
RBF_GRID = (0.25, 0.5, 1.0, 2.0, 4.0)    # RBF gamma = g / median squared distance
LAM_GRID = (1e-6, 1e-3, 1e-1)            # ridge, both kernels


def features(inp, prob, z):
    yn, y = prob.y_names, np.round(z[: prob.ny])
    kind = {m["name"]: m["kind"] for m in inp.struct["materials"]}

    def level(prefix):
        idx = [i for i, a in enumerate(yn) if a.startswith(prefix)]
        on = [k for k, i in enumerate(idx) if y[i] > 0.5]
        return (on[0] + 1) / len(idx) if on else 0.0

    def share(k):
        idx = [i for i, a in enumerate(yn) if a.startswith("con.") and kind[a[4:]] == k]
        return float(y[idx].mean()) if idx else 0.0

    x = prob.probs @ z[prob.ny:].reshape(prob.K, prob.nx)       # expected flows
    get = dict(zip(prob.x_names, x)).get
    tot = {m: get(f"q.{m}") + get(f"qc.{m}", 0.0) for m in inp.mats()}
    charge = sum(tot.values()) or 1.0
    power = (get("g") + get("sol") + get("ppa")) or 1.0
    heat = (get("fo") + get("ng")) or 1.0
    f = [level("sol."), level("ppa."), y[prob.iy("whr")], y[prob.iy("pre")], y[prob.iy("hot")],
         y[prob.iy("gas")], y[prob.iy("shred")], share("dri"), share("scrap"),
         sum(tot[m] for m in inp.scrap()) / charge, (get("sol") + get("ppa")) / power, get("ng") / heat]
    return np.pi * np.clip(np.array(f, float), 0.0, 1.0)


class KRR:
    def __init__(self, kernel, lam=1e-6):
        self.kernel, self.lam = kernel, lam

    def fit(self, X, y):
        self.X = np.asarray(X, float)
        y = np.asarray(y, float)
        self.mu = y.mean()
        K = self.kernel(self.X)
        self.alpha = np.linalg.solve(K + self.lam * np.eye(len(y)), y - self.mu)
        return self

    def predict(self, Xn):
        return self.kernel(np.asarray(Xn, float), self.X) @ self.alpha + self.mu


def loo_residuals(K, y, lam):
    """Closed-form LOO residuals of the centred KRR: r_i = alpha_i / C_ii, C = (K + lam I)^-1, alpha = C (y - mu).
    "Refit without i" keeps mu = mean(y) of the full archive fixed and drops point i from the kernel fit only;
    under that definition the formula is exact."""
    y = np.asarray(y, float)
    C = np.linalg.inv(K + lam * np.eye(len(y)))
    return (C @ (y - y.mean())) / np.diag(C)


def select(gram, grid, y, lams=LAM_GRID):
    """(bandwidth, lam) with the smallest mean squared LOO residual. gram(b) -> K, built once per bandwidth.
    Bandwidth outer, lam inner, both in listed order; ties (and non-finite errors) keep the earlier pair."""
    best = (np.inf, grid[0], lams[0])
    for b in grid:
        K = gram(b)
        for lam in lams:
            e = float(np.mean(loo_residuals(K, y, lam) ** 2))
            if e < best[0]:
                best = (e, b, lam)
    return best[1], best[2]
