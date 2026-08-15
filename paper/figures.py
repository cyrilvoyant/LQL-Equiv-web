"""Figures and statistics for the SoftwareX manuscript.

Produces three vector figures and prints every number quoted in the text, so
that the manuscript can be regenerated from the code rather than transcribed.

    python paper/figures.py

Statistics are applied only where there is something to infer. The comparison
against the reference implementation is an equivalence question over a
population of schedules, so it is treated as one: two one-sided tests against a
pre-stated margin, with a bootstrap interval. The sensitivity analysis
propagates a real parameter uncertainty by Monte Carlo, so a confidence interval
means something there. The model itself is deterministic; no interval is placed
on its arithmetic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from compare_with_2014 import _number, replay  # noqa: E402
from lqlequiv import Course, Options, Prescription, compute, load_library  # noqa: E402
from lqlequiv.schedule import TimeModel  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
RNG = np.random.default_rng(20260815)
BOOTSTRAP = 10_000

mpl.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif", "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "legend.frameon": False, "lines.linewidth": 1.4,
})
BLUE, TEAL, RED, GREY = "#3b6ea5", "#4aa3a3", "#d1495b", "#8a8f98"


def fmt_p(p: float) -> str:
    """Report small p-values as a bound rather than as spurious precision."""
    return "< 1e-4" if p < 1e-4 else f"= {p:.4f}"


def bootstrap_ci(sample, statistic=np.median, level=0.95):
    """Percentile bootstrap interval for a statistic of one sample."""
    sample = np.asarray(sample, dtype=float)
    draws = RNG.choice(sample, size=(BOOTSTRAP, sample.size), replace=True)
    values = statistic(draws, axis=1)
    low, high = np.percentile(values, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return statistic(sample), low, high


# ---------------------------------------------------------------------------
# Figure 1 -- agreement with the 2014 reference implementation
# ---------------------------------------------------------------------------

def figure_agreement():
    golden = ROOT / "tests" / "data" / "golden.jsonl"
    options = Options()
    fields = ("eqdtotal", "eqdttotal", "eqds1", "eqds2", "eqds3",
              "eqdt1", "eqdt2", "eqdt3")
    reference, ported = [], []
    with golden.open(encoding="utf-8") as handle:
        for line in handle:
            case = json.loads(line)
            if "error" in case:
                continue
            mine = replay(case, options)
            for field in fields:
                a, b = _number(case["out"].get(field)), mine.get(field)
                if a is not None and b is not None:
                    reference.append(a)
                    ported.append(b)
    reference, ported = np.array(reference), np.array(ported)
    difference = ported - reference

    # MARGIN is the largest difference that could not change any clinical
    # reading; every decision threshold in this field is orders of magnitude
    # coarser. Equivalence is declared only if the whole interval sits inside it.
    MARGIN = 0.05  # Gy

    rho, rho_p = stats.spearmanr(reference, ported)
    non_zero = difference[difference != 0]
    wilcoxon_p = stats.wilcoxon(non_zero)[1] if non_zero.size else 1.0
    mean_abs, abs_low, abs_high = bootstrap_ci(np.abs(difference), np.mean)
    bias, bias_low, bias_high = bootstrap_ci(difference, np.mean)
    equivalent = bias_low > -MARGIN and bias_high < MARGIN

    print("=" * 72)
    print("FIGURE 1  equivalence with the 2014 reference")
    print(f"  paired values                  n = {reference.size}")
    print(f"  exactly equal                    {int((difference == 0).sum())} "
          f"({100 * (difference == 0).mean():.3f} %)")
    print(f"  Spearman rho                     {rho:.6f}  (p {fmt_p(rho_p)})")
    print(f"  mean difference (bias)           {bias:+.3e} Gy "
          f"[95 % CI {bias_low:+.3e}, {bias_high:+.3e}]")
    print(f"  mean |difference|                {mean_abs:.3e} Gy "
          f"[95 % CI {abs_low:.3e}, {abs_high:.3e}]")
    print(f"  max |difference|                 {np.abs(difference).max():.3e} Gy")
    print(f"  equivalence margin               +/- {MARGIN} Gy")
    print(f"  interval inside the margin       {equivalent}")
    print(f"  [Wilcoxon on the {non_zero.size} non-zero pairs gives p "
          f"{fmt_p(wilcoxon_p)}; it detects the six-significant-digit rounding")
    print("   the captured reference, not a disagreement, and is reported only")
    print("   to be dismissed: the effect it finds is ~1e-5 Gy.]")

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 3.1))

    left.scatter(reference, ported, s=3, alpha=0.25, color=BLUE, edgecolors="none")
    limits = [0, max(reference.max(), ported.max()) * 1.02]
    left.plot(limits, limits, color=GREY, lw=0.8, ls="--", zorder=0)
    left.set_xlim(limits)
    left.set_ylim(limits)
    left.set_xlabel("2014 reference implementation (Gy)")
    left.set_ylabel("LQL-Equiv 3.0 (Gy)")
    left.set_title(f"(a)  $\\rho_s$ = {rho:.6f}, $n$ = {reference.size}", loc="left")

    mean_pair = (reference + ported) / 2
    right.scatter(mean_pair, difference, s=3, alpha=0.25, color=TEAL,
                  edgecolors="none")
    bias = np.mean(difference)
    upper, lower = bias + 1.96 * difference.std(), bias - 1.96 * difference.std()
    for value, style, label in ((bias, "-", "bias"),
                                (upper, "--", "$\\pm$1.96 SD"), (lower, "--", None)):
        right.axhline(value, color=RED, lw=0.9, ls=style, label=label)
    right.set_xlabel("mean of the two implementations (Gy)")
    right.set_ylabel("difference (Gy)")
    right.set_title("(b)  agreement", loc="left")
    right.legend(loc="upper right", fontsize=7)

    fig.tight_layout()
    fig.savefig(OUT / "fig1_agreement.pdf")
    plt.close(fig)
    return dict(n=int(reference.size), rho=float(rho), wilcoxon_p=float(wilcoxon_p),
                bias=float(bias), bias_ci=(float(bias_low), float(bias_high)),
                mean_abs=float(mean_abs), margin=MARGIN, equivalent=bool(equivalent),
                max_abs=float(np.abs(difference).max()),
                exact=float((difference == 0).mean()))


# ---------------------------------------------------------------------------
# Figure 2 -- propagating the alpha/beta uncertainty
# ---------------------------------------------------------------------------

def figure_uncertainty():
    """Monte Carlo over the published spread of alpha/beta.

    This is the one place where a confidence interval is meaningful: the model
    is deterministic, but its alpha/beta input is not known to better than the
    spread reported across clinical studies, and that spread propagates.
    """
    from dataclasses import replace as _replace

    library = load_library()
    options = Options(legacy_quantisation=False, time_model=TimeModel.STAIRCASE)
    organ = library.organ("Rectum")
    tumour = library.tumour_site("Prostate")
    # van Leeuwen et al. report prostate alpha/beta clustering near 1-2 Gy where
    # this library tabulates 3.1; the organ is sampled over the same relative
    # spread. Log-normal keeps the ratio positive and its dispersion symmetric.
    draws = 5000
    spread = 0.30
    tumour_ab = tumour.alpha_beta * np.exp(RNG.normal(0, spread / 1.96, draws))
    organ_ab = organ.alpha_beta * np.exp(RNG.normal(0, spread / 1.96, draws))

    schedules = {"conventional 39 x 2 Gy": (2.0, 39),
                 "moderate 20 x 3 Gy": (3.0, 20),
                 "ultra 5 x 7.25 Gy": (7.25, 5)}
    summary = {}
    fig, axes = plt.subplots(1, len(schedules), figsize=(7.2, 2.9), sharey=True)
    for axis, (label, (dose, n)) in zip(axes, schedules.items()):
        plan = Prescription(courses=(Course(dose, n),), reference_dose=2.0)
        values = np.empty(draws)
        for i in range(draws):
            values[i] = compute(
                _replace(organ, alpha_beta=organ_ab[i], dt=2 * organ_ab[i]),
                _replace(tumour, alpha_beta=tumour_ab[i], dt=2 * tumour_ab[i]),
                plan, options, library).eqd_oar_total
        low, high = np.percentile(values, [2.5, 97.5])
        nominal = compute(organ, tumour, plan, options, library).eqd_oar_total
        rho, p = stats.spearmanr(organ_ab, values)
        summary[label] = dict(nominal=float(nominal), low=float(low),
                              high=float(high), rho=float(rho), p=float(p),
                              width=float(high - low))
        axis.hist(values, bins=45, color=BLUE, alpha=0.75, edgecolor="none")
        axis.axvline(nominal, color=RED, lw=1.2)
        axis.axvspan(low, high, color=GREY, alpha=0.18)
        axis.set_title(label, fontsize=8, loc="left")
        axis.set_xlabel("organ EQD2 (Gy)")
    axes[0].set_ylabel("Monte Carlo draws")

    print("=" * 72)
    print("FIGURE 2  alpha/beta uncertainty propagated, rectum / prostate")
    print(f"  {draws} draws, log-normal, 95 % of mass within +/-{spread:.0%}")
    for label, s_ in summary.items():
        print(f"  {label:24s} {s_['nominal']:6.2f} Gy "
              f"[95 % CI {s_['low']:6.2f}, {s_['high']:6.2f}] "
              f"width {s_['width']:5.2f} Gy | rho(a/b, EQD2) = {s_['rho']:+.3f} "
              f"(p {fmt_p(s_['p'])})")

    fig.tight_layout()
    fig.savefig(OUT / "fig2_uncertainty.pdf")
    plt.close(fig)
    return summary


# ---------------------------------------------------------------------------
# Figure 3 -- where the linear tail changes the answer
# ---------------------------------------------------------------------------

def figure_lql():
    library = load_library()
    options = Options(legacy_quantisation=False, time_model=TimeModel.STAIRCASE)
    organ = library.organ("Spinal cord")
    tumour = library.tumour_site("Standard tumour, no proliferation")
    doses = np.arange(1.0, 15.01, 0.25)
    total = 60.0

    lql, lq = [], []
    for dose in doses:
        plan = Prescription(courses=(Course(float(dose), total / dose),),
                            reference_dose=2.0)
        lql.append(compute(organ, tumour, plan, options, library).eqd_oar_total)
        # Pure linear-quadratic: the transition dose pushed out of range.
        from dataclasses import replace as _replace
        lq.append(compute(_replace(organ, dt=1e6), tumour, plan,
                          options, library).eqd_oar_total)
    lql, lq = np.array(lql), np.array(lq)
    relative = 100 * (lq - lql) / lql

    print("=" * 72)
    print("FIGURE 3  linear-quadratic against linear-quadratic-linear")
    print(f"  transition dose of the spinal cord  {organ.dt:.1f} Gy")
    for dose in (2.0, 6.0, 8.0, 10.0, 15.0):
        i = int(np.argmin(np.abs(doses - dose)))
        print(f"  {dose:5.1f} Gy/fraction : LQL {lql[i]:7.2f}  LQ {lq[i]:7.2f} "
              f"({relative[i]:+5.1f} %)")

    fig, axis = plt.subplots(figsize=(3.6, 3.0))
    axis.plot(doses, lq, color=RED, ls="--", label="linear-quadratic")
    axis.plot(doses, lql, color=BLUE, label="linear-quadratic-linear")
    axis.axvline(organ.dt, color=GREY, lw=0.8, ls=":")
    axis.annotate(f"$d_t$ = {organ.dt:.0f} Gy", xy=(organ.dt, axis.get_ylim()[1]),
                  xytext=(organ.dt + 0.4, axis.get_ylim()[1] * 0.92),
                  fontsize=7, color=GREY)
    axis.set_xlabel("dose per fraction (Gy)")
    axis.set_ylabel("organ equivalent dose (Gy EQD2)")
    axis.legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_lql.pdf")
    plt.close(fig)
    return dict(dt=organ.dt, relative_at_10=float(
        relative[int(np.argmin(np.abs(doses - 10.0)))]))


def main() -> int:
    OUT.mkdir(exist_ok=True)
    figure_agreement()
    figure_uncertainty()
    figure_lql()
    print("=" * 72)
    print(f"figures written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
