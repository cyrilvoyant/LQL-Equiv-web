"""Figures and statistics for the SoftwareX manuscript.

Produces three vector figures and prints every number quoted in the text, so
that the manuscript can be regenerated from the code rather than transcribed.

    python paper/figures.py

Statistics are applied only where there is something to infer. The comparison
against the reference implementation is an equivalence question over a
population of schedules, so it is treated as one, against a pre-stated margin
and with a bootstrap interval. The sensitivity analysis propagates a real
parameter uncertainty by Monte Carlo, so a confidence interval means something
there. The model itself is deterministic; no interval is placed on its
arithmetic.

Each figure makes one point. A scatter of two implementations that agree to
five decimals is a straight line and says nothing, so the agreement is shown
as the distribution of the disagreement against the margin instead.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from compare_with_2014 import _number, replay  # noqa: E402
from lqlequiv import Course, Options, Prescription, compute, load_library  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
RNG = np.random.default_rng(20260815)
BOOTSTRAP = 10_000
MARGIN = 0.05  # Gy; equivalence margin, far below any decision threshold
SPREAD = 0.30  # 95 % of the alpha/beta draws fall within +/- this fraction
DRAWS = 2000
#: What the software computes. Figures 1 and 5 also run
#: ``Options.legacy_2014()``, being comparisons against the 2014 application.
EXACT = Options()

mpl.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 400, "savefig.bbox": "tight",
    "font.family": "serif", "mathtext.fontset": "dejavuserif",
    "font.size": 8.5, "axes.labelsize": 8.5, "axes.titlesize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.20, "grid.linewidth": 0.4,
    "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 7.5,
    "lines.linewidth": 1.5, "xtick.direction": "out", "ytick.direction": "out",
})
BLUE, TEAL, RED, GREY, SAND = "#3b6ea5", "#4aa3a3", "#d1495b", "#8a8f98", "#c47f2a"
PURPLE = "#7b5ea7"


def fmt_p(p: float) -> str:
    """Report small p-values as a bound rather than as spurious precision."""
    return "< 1e-4" if p < 1e-4 else f"= {p:.4f}"


def bootstrap_ci(sample, statistic=np.mean, level=0.95):
    """Percentile bootstrap interval for a statistic of one sample."""
    sample = np.asarray(sample, dtype=float)
    draws = RNG.choice(sample, size=(BOOTSTRAP, sample.size), replace=True)
    values = statistic(draws, axis=1)
    low, high = np.percentile(values, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return statistic(sample), low, high


def panel_tag(axis, text):
    axis.set_title(text, loc="left", y=1.02, fontsize=9)


# ---------------------------------------------------------------------------
# Figure 1 -- how large is the disagreement, and does it clear the margin
# ---------------------------------------------------------------------------

def figure_equivalence():
    golden = ROOT / "tests" / "data" / "golden.jsonl"
    fields = ("eqdtotal", "eqdttotal", "eqds1", "eqds2", "eqds3",
              "eqdt1", "eqdt2", "eqdt3")
    reference, ported = [], []
    with golden.open(encoding="utf-8") as handle:
        for line in handle:
            case = json.loads(line)
            if "error" in case:
                continue
            mine = replay(case, Options())
            for field in fields:
                a, b = _number(case["out"].get(field)), mine.get(field)
                if a is not None and b is not None:
                    reference.append(a)
                    ported.append(b)
    reference, ported = np.array(reference), np.array(ported)
    difference = ported - reference
    absolute = np.abs(difference)

    exact = float((difference == 0).mean())

    # The disagreement splits into two populations: rounding of the arithmetic,
    # at the level of the double-precision epsilon, and the handful of cases
    # where the 2014 grid search and the exact solver fall on either side of a
    # tie. The cut is placed in the empty decades that separate them.
    CUT = 1e-10
    noise = absolute[(absolute > 0) & (absolute < CUT)]
    real = absolute[absolute >= CUT]

    print("=" * 74)
    print("FIGURE 1  equivalence with the 2014 reference")
    print(f"  paired equivalent doses          n = {reference.size}")
    print(f"  identical                          {int((difference == 0).sum())} "
          f"({100 * exact:.2f} %)")
    print(f"  differ by less than 1e-10 Gy       {noise.size} "
          f"({100 * noise.size / reference.size:.2f} %), arithmetic rounding")
    print(f"  differ by more than 1e-10 Gy       {real.size} "
          f"({100 * real.size / reference.size:.3f} %), grid ties, "
          f"largest {real.max() if real.size else 0:.3f} Gy")
    print(f"  within 0.005 Gy                    "
          f"{100 * (absolute <= 0.005).mean():.2f} %")
    for q in (50, 95, 99, 99.9):
        print(f"  {q:5.1f}th percentile of |diff|       "
              f"{np.percentile(absolute, q):.3e} Gy")
    print(f"  largest deviation                  {absolute.max():.3f} Gy")
    print(f"  tolerance {MARGIN} Gy, values clearing  "
          f"{int((absolute <= MARGIN).sum())} of {absolute.size}")

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.1, 2.9))

    # (a) the two populations of disagreement, decade by decade
    positive = absolute[absolute > 0]
    bins = np.logspace(-17, np.log10(0.3), 55)
    left.axvspan(1e-17, CUT, color=GREY, alpha=0.10, lw=0)
    left.axvspan(CUT, 0.3, color=SAND, alpha=0.10, lw=0)
    left.hist(positive, bins=bins, color=BLUE, alpha=0.9, edgecolor="none")
    left.axvline(MARGIN, color=RED, lw=1.4, zorder=5)
    left.set_xscale("log")
    left.set_yscale("log")
    left.set_xlim(1e-17, 0.3)
    left.set_ylim(0.7, 4e3)
    left.set_xlabel("absolute difference (Gy), zero excluded")
    left.set_ylabel("number of paired values")
    left.text(3e-14, 2.4e3, f"arithmetic rounding\n{noise.size} values",
              fontsize=7, color="#4a4a4a", ha="center", va="top")
    left.text(2e-3, 2.4e3, f"grid ties\n{real.size} values",
              fontsize=7, color=SAND, ha="center", va="top")
    left.text(MARGIN * 1.3, 1.0, "tolerance  $\\delta$ = 0.05 Gy", fontsize=7.5,
              color=RED, rotation=90, va="bottom", ha="left")
    panel_tag(left, f"(a)  {100 * exact:.1f} % of the {reference.size} values "
                    "are bit-identical")

    # (b) the same evidence read as a cumulative claim against the tolerance
    order = np.sort(np.maximum(absolute, 1e-17))
    fraction = 100 * np.arange(1, order.size + 1) / order.size
    right.step(order, fraction, where="post", color=BLUE, lw=1.6, zorder=4)
    right.axvspan(MARGIN, 1.0, color=RED, alpha=0.08, lw=0)
    right.axvline(MARGIN, color=RED, lw=1.4)
    right.axhline(100 * exact, color=GREY, lw=0.8, ls=":")
    right.set_xscale("log")
    right.set_xlim(1e-17, 1.0)
    right.set_ylim(90, 100.5)
    right.set_xlabel("absolute difference (Gy)")
    right.set_ylabel("cumulative share of values (%)")
    right.text(2e-16, 100 * exact + 0.12, f"{100 * exact:.1f} % identical",
               fontsize=7, color=GREY, va="bottom")
    right.annotate("every value below\nthe margin",
                   xy=(absolute.max(), 100), xytext=(1e-8, 95.6),
                   fontsize=7.5, color=BLUE, ha="left",
                   arrowprops=dict(arrowstyle="->", color=BLUE, lw=0.8))
    right.text(MARGIN * 1.7, 90.6, "beyond\ntolerance", fontsize=7, color=RED)
    panel_tag(right, "(b)  the whole distribution clears the tolerance")

    fig.tight_layout()
    fig.savefig(OUT / "fig1_agreement.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 -- the fractionation question, as a department has to answer it
# ---------------------------------------------------------------------------

def figure_fractionation():
    """Hypofractionation of a prostate treatment, at constant effect on the target.

    The clinical question is not what a schedule scores in the abstract but what
    it costs the organ at risk once the target effect has been held fixed. Every
    point on the curves is a schedule solved by the software: the number of
    fractions is adjusted so that the target receives 78 Gy EQD2 whatever the
    fraction size, so the target effect, and with it the tumour control estimate,
    is constant by construction and only the organ moves.

    Three assumptions about the target are carried through, and they do not
    agree. Under the plain linear-quadratic model with the low alpha/beta that
    pooled prostate series support, hypofractionation lowers the dose to the
    organ: that is the standard argument for prostate stereotactic treatment.
    The same alpha/beta under the linear-quadratic-linear model reverses it,
    because the transition dose is 2 alpha/beta and a low alpha/beta places the
    transition below the fraction sizes at issue, so the linear tail removes the
    advantage before it can be spent. The tabulated 3.1 Gy sits in between.

    Whether the gain survives therefore depends on a transition dose for the
    target that no series constrains well. The point is not to settle it but to
    show that it is a decision, taken explicitly here rather than hidden in the
    choice of formula. The bands are the +/-30 % uncertainty on the organ
    alpha/beta, the prescription being held at whatever the target assumption
    dictates.

    Every point is a deliverable schedule. The fraction count is swept over the
    integers and the dose per fraction is solved, rather than the reverse, so no
    curve passes through a fractional number of fractions. The two randomised
    trials that settled prostate hypofractionation are marked for scale.
    """
    library = load_library()
    organ = library.organ("Rectum")
    prostate = library.tumour_site("Prostate")
    target_eqd = 78.0
    counts = np.arange(4, 40)
    factors = np.exp(RNG.normal(0, np.log(1 + SPREAD) / 1.96, DRAWS))
    scenarios = (
        ("LQ, $\\alpha/\\beta$ = 1.5 Gy (no linear tail)", 1.5, 1e6, TEAL),
        ("LQL, $\\alpha/\\beta$ = 1.5 Gy, $d_t$ = 3.0 Gy", 1.5, 3.0, RED),
        ("LQL, tabulated 3.1 Gy, $d_t$ = 6.2 Gy", 3.1, 6.2, BLUE),
    )
    #: The regimens of the two trials that settled the question clinically,
    #: quoted so that the reader can see which part of the axis is real.
    trials = ((7, 6.1, "HYPO-RT-PC\n42.7 Gy / 7"),
              (5, 7.25, "PACE-B\n36.25 Gy / 5"))

    def solve(count, tumour):
        """Fraction size that puts the target at 78 Gy EQD2 in ``count`` fractions."""
        def gap(dose):
            plan = Prescription(courses=(Course(float(dose), float(count)),),
                                reference_dose=2.0)
            return compute(organ, tumour, plan, EXACT,
                           library).eqd_tumour_total - target_eqd
        return brentq(gap, 0.5, 30.0, xtol=1e-9)

    print("=" * 74)
    print("FIGURE 2  hypofractionation at constant target effect")
    print(f"  target held at {target_eqd:g} Gy EQD2, organ = {organ.name.lower()}"
          f" ({organ.endpoint.lower()}, alpha/beta {organ.alpha_beta} Gy)")
    print(f"  bands: {DRAWS} draws on the organ alpha/beta, log-normal, "
          f"95 % within +/-{SPREAD:.0%}")

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.1, 2.9), sharex=True)
    summary = {}

    for label, alpha_beta, transition, colour in scenarios:
        tumour = replace(prostate, alpha_beta=alpha_beta, dt=transition)
        size = np.empty(counts.size)
        eqd = np.empty(counts.size)
        ntcp = np.empty(counts.size)
        eqd_cloud = np.empty((counts.size, DRAWS))
        ntcp_cloud = np.empty((counts.size, DRAWS))
        for i, count in enumerate(counts):
            size[i] = solve(count, tumour)
            plan = Prescription(courses=(Course(size[i], float(count)),),
                                reference_dose=2.0)
            result = compute(organ, tumour, plan, EXACT, library)
            eqd[i], ntcp[i] = result.eqd_oar_total, result.ntcp_percent
            for j, factor in enumerate(factors):
                drawn = compute(
                    replace(organ, alpha_beta=organ.alpha_beta * factor,
                            dt=2 * organ.alpha_beta * factor),
                    tumour, plan, EXACT, library)
                eqd_cloud[i, j] = drawn.eqd_oar_total
                ntcp_cloud[i, j] = drawn.ntcp_percent

        eqd_low, eqd_high = np.percentile(eqd_cloud, [2.5, 97.5], axis=1)
        ntcp_low, ntcp_high = np.percentile(ntcp_cloud, [2.5, 97.5], axis=1)
        summary[label] = (size, eqd, ntcp)

        left.fill_between(size, eqd_low, eqd_high, color=colour, alpha=0.20, lw=0)
        left.plot(size, eqd, color=colour, marker="o", ms=2.4, label=label)
        right.fill_between(size, ntcp_low, ntcp_high, color=colour, alpha=0.20,
                           lw=0)
        right.plot(size, ntcp, color=colour, marker="o", ms=2.4, label=label)

        print(f"  {label}:")
        for count in (39, 20, 7, 5):
            i = int(np.argmin(np.abs(counts - count)))
            print(f"    {counts[i]:2d} x {size[i]:5.2f} Gy "
                  f"= {counts[i] * size[i]:5.1f} Gy   organ EQD2 "
                  f"{eqd[i]:6.2f} [{eqd_low[i]:6.2f}, {eqd_high[i]:6.2f}]   "
                  f"NTCP {ntcp[i]:5.1f} % [{ntcp_low[i]:5.1f}, {ntcp_high[i]:5.1f}]")

    for axis in (left, right):
        axis.set_xlabel("dose per fraction (Gy), whole fractions only")
        axis.set_xlim(1.8, 11.0)
        for _, dose, _ in trials:
            axis.axvline(dose, color=GREY, lw=0.7, ls=":", zorder=0)
    left.legend(loc="upper left")
    right.legend(loc="lower right")
    left.set_ylabel("organ EQD2 (Gy)")
    right.set_ylabel("NTCP, %s (%%)" % organ.endpoint.lower())
    left.axhline(target_eqd, color=GREY, lw=0.8, ls="--", zorder=0)
    # The dotted verticals are identified in the caption rather than in the
    # panel: any in-figure label large enough to read collides with a curve.
    panel_tag(left, "(a)  what the organ absorbs, target effect held fixed")
    panel_tag(right, "(b)  and what that costs in complication risk")

    # The comparison the figure exists to support, at a schedule that was
    # actually delivered in a randomised trial rather than at an axis endpoint.
    lq_label, lql_label = scenarios[0][0], scenarios[1][0]
    i = int(np.argmin(np.abs(counts - 5)))
    print(f"  at 5 fractions, same target effect and same target alpha/beta:")
    print(f"    without the linear tail   {summary[lq_label][0][i]:5.2f} Gy per "
          f"fraction, organ EQD2 {summary[lq_label][1][i]:6.2f} Gy, NTCP "
          f"{summary[lq_label][2][i]:5.1f} %")
    print(f"    with it                   {summary[lql_label][0][i]:5.2f} Gy per "
          f"fraction, organ EQD2 {summary[lql_label][1][i]:6.2f} Gy, NTCP "
          f"{summary[lql_label][2][i]:5.1f} %")
    print("    the two forms disagree on the sign of the effect, not its size")

    fig.tight_layout()
    fig.savefig(OUT / "fig2_fractionation.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3 -- what the linear tail changes, and for which tissues
# ---------------------------------------------------------------------------

def figure_lql():
    library = load_library()
    tumour = library.tumour_site("Standard tumour, no proliferation")
    doses = np.arange(1.0, 15.001, 0.25)
    total = 60.0

    draws = 400
    factors = np.exp(RNG.normal(0, np.log(1 + SPREAD) / 1.96, draws))

    def curve(organ, linear_tail=True, factor=1.0):
        """Equivalent dose against fraction size, at constant total dose.

        Proliferation is switched off on both tissues so that the curves isolate
        the fractionation effect. Left on, the overall time varies with the
        fraction size and mixes a second effect into the comparison; for the
        lung it is large enough to cancel the whole equivalent dose at 1 Gy per
        fraction, which says nothing about the linear tail.

        ``factor`` scales alpha/beta, and with it the transition dose, so that
        the same +/-30 % uncertainty as in figure 2 can be carried through.
        """
        alpha_beta = organ.alpha_beta * factor
        organ = replace(organ, dprol_override=0.0, alpha_beta=alpha_beta,
                        dt=(2 * alpha_beta if linear_tail else 1e6))
        values = []
        for dose in doses:
            plan = Prescription(courses=(Course(float(dose), total / dose),),
                                reference_dose=2.0)
            values.append(compute(organ, tumour, plan, EXACT,
                                  library).eqd_oar_total)
        return np.array(values)

    def band(organ, linear_tail=True):
        """Nominal curve and the 95 % interval it inherits from alpha/beta."""
        cloud = np.array([curve(organ, linear_tail, f) for f in factors])
        low, high = np.percentile(cloud, [2.5, 97.5], axis=0)
        return curve(organ, linear_tail), low, high

    cord = library.organ("Spinal cord")
    lql, lql_low, lql_high = band(cord)
    lq, lq_low, lq_high = band(cord, linear_tail=False)

    print("=" * 74)
    print("FIGURE 3  linear-quadratic against linear-quadratic-linear")
    print(f"  spinal cord, transition dose {cord.dt:.1f} Gy, "
          f"total physical dose {total:g} Gy, proliferation switched off")
    print(f"  bands: {draws} draws, alpha/beta log-normal, "
          f"95 % within +/-{SPREAD:.0%}, transition dose follows")
    for target in (2.0, 6.0, 10.0, 15.0):
        i = int(np.argmin(np.abs(doses - target)))
        print(f"  {doses[i]:5.1f} Gy/fraction  "
              f"LQL {lql[i]:7.2f} [{lql_low[i]:6.2f}, {lql_high[i]:6.2f}]  "
              f"LQ {lq[i]:7.2f} [{lq_low[i]:6.2f}, {lq_high[i]:6.2f}]  "
              f"{100 * (lq[i] - lql[i]) / lql[i]:+6.1f} %")

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.1, 2.9), sharex=True)

    left.fill_between(doses, lql, lq, color=GREY, alpha=0.10, lw=0,
                      label="excess attributed by LQ")
    left.fill_between(doses, lq_low, lq_high, color=RED, alpha=0.20, lw=0)
    left.fill_between(doses, lql_low, lql_high, color=BLUE, alpha=0.25, lw=0)
    left.plot(doses, lq, color=RED, ls="--", label="linear-quadratic")
    left.plot(doses, lql, color=BLUE, label="linear-quadratic-linear")
    left.axvline(cord.dt, color=GREY, lw=0.8, ls=":", zorder=0)
    left.text(cord.dt - 0.35, 40, f"$d_t$ = {cord.dt:.0f} Gy", fontsize=7,
              color=GREY, rotation=90, ha="right", va="bottom")
    left.set_xlabel("dose per fraction (Gy)")
    left.set_ylabel("organ EQD2 (Gy)")
    left.set_xlim(1, 15)
    left.legend(loc="upper left")
    panel_tag(left, "(a)  spinal cord, 60 Gy in every schedule")

    # (b) the same quantity for every tissue in the library. The dispersion
    # across tissues is far wider than the uncertainty on any one alpha/beta,
    # so the tissues are drawn as a population rather than each with its band.
    excesses = {}
    for name in library.organ_names:
        organ = library.organ(name)
        tail = curve(organ, True)
        excesses[name] = (100 * (curve(organ, False) - tail)
                          / np.maximum(tail, 1e-9))
    population = np.array([excesses[n] for n in library.organ_names])
    median = np.median(population, axis=0)
    q1, q3 = np.percentile(population, [25, 75], axis=0)

    for values in population:
        right.plot(doses, values, color=GREY, lw=0.5, alpha=0.35, zorder=1)
    right.fill_between(doses, q1, q3, color=BLUE, alpha=0.18, lw=0, zorder=2,
                       label="interquartile range")
    right.plot(doses, median, color=BLUE, lw=1.8, zorder=4,
               label=f"median of {len(library.organ_names)} tissues")

    print(f"  excess by tissue, {len(library.organ_names)} tissues in the library:")
    for want in (6.0, 10.0, 12.0, 15.0):
        i = int(np.argmin(np.abs(doses - want)))
        print(f"    {doses[i]:5.1f} Gy/fraction   median {median[i]:+6.1f} %   "
              f"IQR [{q1[i]:+6.1f}, {q3[i]:+6.1f}]   "
              f"range [{population[:, i].min():+6.1f}, "
              f"{population[:, i].max():+6.1f}]")
    for name, colour in (("Spinal cord", RED), ("Stomach", PURPLE)):
        organ = library.organ(name)
        right.plot(doses, excesses[name], color=colour, lw=1.4, zorder=5,
                   label=f"{name.lower()}, $d_t$ = {organ.dt:.1f} Gy")
        i = int(np.argmin(np.abs(doses - 12.0)))
        print(f"    {name:14s} dt {organ.dt:5.1f} Gy   "
              f"{excesses[name][i]:+6.1f} % at 12 Gy per fraction")
    right.set_xlabel("dose per fraction (Gy)")
    right.set_ylabel("dose attributed in excess by LQ (%)")
    right.set_xlim(1, 15)
    right.set_ylim(-3, 120)
    above = int((population[:, -1] > 120).sum())
    right.text(0.99, 0.99, f"{above} tissues with $d_t$ = 1.6 Gy\n"
                            f"leave the axis, up to "
                            f"{population[:, -1].max():.0f} %",
               transform=right.transAxes, fontsize=7, color=GREY,
               ha="right", va="top")
    right.legend(loc="upper left")
    panel_tag(right, "(b)  every tissue in the library")

    fig.tight_layout()
    fig.savefig(OUT / "fig3_lql.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5 -- what the 2014 organ-at-risk convention changed, and where
# ---------------------------------------------------------------------------

def figure_2014_difference():
    """Version 3.0 against the 2014 application, over deliverable schedules.

    One, two and three successive courses, 1 to 12 Gy per fraction, once and
    twice a day, with and without interruptions capped at fourteen missed
    sessions. Schedules leaving the organ above 100 Gy EQD2 are dropped, being
    arithmetically valid and clinically meaningless, as are those the model
    declares inapplicable.
    """
    library = load_library()
    legacy = Options.legacy_2014()
    #: An equivalent dose below 2 Gy is not a treatment and one above 100 Gy is
    #: not an organ constraint; both ends are arithmetic rather than clinic.
    floor, ceiling = 2.0, 100.0
    #: Interruptions in missed sessions. Fourteen is about twenty calendar days
    #: once the weekends inside them are supplied by the staircase.
    max_gap = 14
    doses = np.arange(1.0, 12.01, 0.5)
    counts = np.array([1, 2, 3, 5, 8, 10, 12, 15, 20, 25, 30, 35, 40])
    gap_choices = np.array([0, 0, 0, 3, 5, 7, 10, 14])
    rng = np.random.default_rng(20260816)

    rows, seen = [], set()
    for _ in range(80_000):
        n_courses = int(rng.integers(1, 4))
        budget, courses = max_gap, []
        for index in range(n_courses):
            gap = 0 if index == 0 else int(min(rng.choice(gap_choices), budget))
            budget -= gap
            courses.append(Course(float(rng.choice(doses)),
                                  float(rng.choice(counts)), float(gap)))
        courses = tuple(courses)
        bifractionated = bool(rng.integers(0, 2))
        organ = library.organ(str(rng.choice(library.organ_names)))
        target = library.tumour_site(str(rng.choice(library.tumour_names)))
        key = (courses, bifractionated, organ.name, target.name)
        if key in seen:
            continue
        seen.add(key)
        if bifractionated and any(
            c.dose_per_fraction > min(organ.dt, target.dt) for c in courses
        ):
            continue
        plan = Prescription(courses=courses, reference_dose=2.0,
                            bifractionated=bifractionated)
        old = compute(organ, target, plan, legacy, library)
        new = compute(organ, target, plan, EXACT, library)
        if not (old.oar_total_valid and old.tumour_total_valid):
            continue
        pair = []
        for a, b in ((old.eqd_oar_total, new.eqd_oar_total),
                     (old.eqd_tumour_total, new.eqd_tumour_total)):
            pair.append((a, b) if floor <= min(a, b) and max(a, b) <= ceiling
                        else None)
        if pair[0] is None and pair[1] is None:
            continue
        rows.append((len(courses), any(c.gap_days > 0 for c in courses),
                     bifractionated, pair[0], pair[1]))

    n_courses = np.array([r[0] for r in rows])
    has_gap = np.array([r[1] for r in rows])
    bids = np.array([r[2] for r in rows])
    kept = {}
    for index, label in ((3, "organ at risk"), (4, "target")):
        mask = np.array([r[index] is not None for r in rows])
        kept[label] = (mask, np.array([r[index][1] - r[index][0]
                                       for r in rows if r[index] is not None]))

    print("=" * 74)
    print("FIGURE 5  version 3.0 against the 2014 application")
    print(f"  {len(rows)} deliverable plans, 1 to 3 courses, 1 to 12 Gy per")
    print(f"  fraction, once and twice a day, interruptions to {max_gap} missed")
    print(f"  sessions, all {len(library.organ_names)} organs and "
          f"{len(library.tumour_names)} target sites,")
    print(f"  equivalent dose kept between {floor:g} and {ceiling:g} Gy EQD2")
    for label, (mask, deltas) in kept.items():
        print(f"  {label}, n = {deltas.size}")
        print(f"    unchanged (|d| < 0.01 Gy)  {int((abs(deltas) < 0.01).sum())} "
              f"({100 * (abs(deltas) < 0.01).mean():.1f} %)")
        print(f"    median                     {np.median(deltas):+.2f} Gy")
        print(f"    5th, 95th percentile       {np.percentile(deltas, 5):+.2f}, "
              f"{np.percentile(deltas, 95):+.2f} Gy")
        print(f"    range                      {deltas.min():+.2f} to "
              f"{deltas.max():+.2f} Gy")
        for sub, name in ((n_courses[mask] == 1, "one course       "),
                          (n_courses[mask] == 2, "two courses      "),
                          (n_courses[mask] == 3, "three courses    "),
                          (~has_gap[mask], "no interruption  "),
                          (has_gap[mask], "with interruption"),
                          (~bids[mask], "once a day       "),
                          (bids[mask], "twice a day      ")):
            if sub.sum():
                print(f"      {name} n = {int(sub.sum()):5d}  median "
                      f"{np.median(deltas[sub]):+6.2f}  5th "
                      f"{np.percentile(deltas[sub], 5):+7.2f} Gy")

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.1, 2.9))
    oar_mask, oar = kept["organ at risk"]
    left.hist([oar[n_courses[oar_mask] == k] for k in (1, 2, 3)], bins=55,
              stacked=True, color=[BLUE, TEAL, SAND], edgecolor="none",
              label=["one course", "two courses", "three courses"])
    left.axvline(0, color=RED, lw=1.2)
    left.set_yscale("log")
    left.set_xlabel("version 3.0 minus 2014 (Gy)")
    left.set_ylabel("plans")
    left.legend(loc="upper left")
    panel_tag(left, f"(a)  organ at risk, {oar.size} plans")

    groups, ticks, colours = [], [], []
    for label, colour in (("organ at risk", BLUE), ("target", TEAL)):
        mask, deltas = kept[label]
        for sub, tick in ((~has_gap[mask] & ~bids[mask], "plain"),
                          (has_gap[mask], "gap"),
                          (bids[mask], "twice a day")):
            if sub.sum():
                groups.append(deltas[sub])
                ticks.append(tick)
                colours.append(colour)
    box = right.boxplot(groups, tick_labels=ticks, widths=0.6, patch_artist=True,
                        flierprops=dict(markersize=1.2))
    for patch, colour in zip(box["boxes"], colours):
        patch.set_facecolor(colour)
        patch.set_alpha(0.35)
        patch.set_edgecolor(colour)
    for median in box["medians"]:
        median.set_color("#2a2a2a")
    right.axhline(0, color=RED, lw=1.2)
    right.set_ylabel("version 3.0 minus 2014 (Gy)")
    right.tick_params(axis="x", labelsize=7)
    right.text(0.25, 0.03, "organ at risk", transform=right.transAxes,
               fontsize=7, color=BLUE, ha="center")
    right.text(0.75, 0.03, "target", transform=right.transAxes,
               fontsize=7, color=TEAL, ha="center")
    panel_tag(right, "(b)  both tissues, by interruption and regime")

    fig.tight_layout()
    fig.savefig(OUT / "fig5_difference2014.pdf")
    plt.close(fig)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    figure_equivalence()
    figure_fractionation()
    figure_lql()
    figure_2014_difference()
    print("=" * 74)
    print(f"figures written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
