"""One objective and one feasibility measure, shared by every heuristic and by scoring."""
import numpy as np

TOL = 1e-6


def evaluate(prob, z):
    r = prob.A @ z
    viol = (np.maximum(0.0, prob.lb - r) / prob.scale).sum()
    viol += (np.maximum(0.0, r - prob.ub) / prob.scale).sum()
    span = np.maximum(1.0, prob.zub - prob.zlb)
    viol += (np.maximum(0.0, prob.zlb - z) / span).sum() + (np.maximum(0.0, z - prob.zub) / span).sum()
    y = z[: prob.ny]
    viol += np.abs(y - np.round(y)).sum()
    return float(prob.c @ z + prob.const), float(prob.e @ z + prob.econst), float(viol)


def is_feasible(viol):
    return viol <= TOL
