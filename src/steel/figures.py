"""Every figure is drawn from result files. No number is typed in here."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def pareto_figure(points, path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot([e for e, _ in points], [c / 1e9 for _, c in points], "o-", color="#2a6f97")
    ax.invert_xaxis()
    ax.set_xlabel("Expected emissions (tCO2e per year)")
    ax.set_ylabel("Expected life cycle cost (billion INR per year)")
    _save(fig, path)


def gap_boxplot(rows, methods, path):
    data = [[float(r["gap_pct"]) for r in rows if r["method"] == m and r["gap_pct"] != ""] or [np.nan] for m in methods]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.boxplot(data, tick_labels=methods)
    ax.set_yscale("symlog", linthresh=1e-3)
    ax.set_ylabel("Gap to exact optimum (%), feasible runs only")
    _save(fig, path)


def scaling_figure(rows, path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for m in sorted({r["method"] for r in rows}):
        sizes = sorted({int(r["n_bin"]) for r in rows if r["method"] == m})
        ax.plot(sizes, [np.median([float(r["seconds"]) for r in rows if r["method"] == m and int(r["n_bin"]) == s])
                        for s in sizes], "o-", label=m)
    sizes = sorted({int(r["n_bin"]) for r in rows})
    ax.plot(sizes, [np.median([float(r["ref_seconds"]) for r in rows if int(r["n_bin"]) == s]) for s in sizes],
            "k--", label="Exact MILP")
    ax.set_yscale("log")
    ax.set_xlabel("Number of yes/no decisions")
    ax.set_ylabel("Median time (s)")
    ax.legend(fontsize=7, ncol=2)
    _save(fig, path)


def moran_figure(z, W, path):
    zs = (z - z.mean()) / z.std()
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(zs, W @ zs, color="#2a6f97")
    ax.axhline(0, color="grey", lw=0.5)
    ax.axvline(0, color="grey", lw=0.5)
    ax.set_xlabel("Delivered carbon intensity (standardised)")
    ax.set_ylabel("Spatial lag")
    _save(fig, path)
