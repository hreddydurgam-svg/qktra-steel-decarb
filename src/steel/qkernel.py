"""Classically simulated quantum kernel: exact state-vector simulation of the ZZ feature map
(second-order Pauli-Z expansion, Havlicek et al. 2019). No hardware, no speed-up claim."""
import numpy as np


def _hadamard_all(a):
    """Apply H to every qubit of state `a` (normalised Walsh-Hadamard transform)."""
    a = a.copy()
    n, h = a.size, 1
    while h < n:
        b = a.reshape(-1, 2, h)
        a = np.stack([b[:, 0] + b[:, 1], b[:, 0] - b[:, 1]], axis=1).reshape(-1)
        h *= 2
    return a / np.sqrt(n)


_STATE_CACHE = {}
_CACHE_LIMIT = 3000   # 2^12 complex amplitudes = 64 kB per state: ~192 MB per process at most


def _diagonal(x):
    n = x.size
    bits = (np.arange(1 << n)[:, None] >> np.arange(n)) & 1
    zs = 1.0 - 2.0 * bits                      # eigenvalue of Z_i: +1 for bit 0, -1 for bit 1
    w = np.pi - x
    A = np.triu(np.outer(w, w), 1)             # pair weights for i < j only
    phase = zs @ x + ((zs @ A) * zs).sum(1)
    return np.exp(1j * phase)


def state(x, reps=2):
    x = np.asarray(x, float)
    key = (reps, x.tobytes())
    if key not in _STATE_CACHE:
        d = _diagonal(x)
        psi = np.zeros(d.size, complex)
        psi[0] = 1.0
        for _ in range(reps):
            psi = d * _hadamard_all(psi)
        if len(_STATE_CACHE) >= _CACHE_LIMIT:
            _STATE_CACHE.clear()
        _STATE_CACHE[key] = psi
    return _STATE_CACHE[key].copy()


def zz_kernel(X, Y=None, reps=2, a=1.0):
    """|<psi(a x)|psi(a y)>|^2; bandwidth `a` scales the features before the map (a = 1: unscaled)."""
    X = np.atleast_2d(np.asarray(X, float))
    S = np.array([state(x, reps) for x in (X if a == 1.0 else a * X)])
    if Y is None:
        T = S
    else:
        Y = np.atleast_2d(np.asarray(Y, float))
        T = np.array([state(y, reps) for y in (Y if a == 1.0 else a * Y)])
    return np.abs(S @ T.conj().T) ** 2


def rbf_kernel(X, Y=None, gamma=1.0):
    X = np.atleast_2d(X)
    Y = X if Y is None else np.atleast_2d(Y)
    d2 = ((X[:, None, :] - Y[None, :, :]) ** 2).sum(-1)
    return np.exp(-gamma * d2)


def median_gamma(X):
    """Median heuristic: gamma = 1 / median of the positive pairwise squared distances in X (1.0 if none)."""
    X = np.atleast_2d(np.asarray(X, float))
    d2 = ((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)
    pos = d2[np.triu_indices(len(X), 1)]
    pos = pos[pos > 0]
    return 1.0 / float(np.median(pos)) if pos.size else 1.0
