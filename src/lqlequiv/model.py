"""Biologically equivalent doses under the linear-quadratic-linear model.

This is a faithful port of the calculation performed by ``pushbutton4_Callback``
in the 2014 MATLAB application (``cyrilvoyant/LQ-Equiv``), covering:

* biologically effective dose (BED) with the linear-quadratic-linear tail of
  Astrahan, the repopulation term of Dale, and the incomplete-repair correction
  of Thames for two fractions a day;
* the equivalent dose in a reference fractionation (EQD, usually EQD2), for both
  the organ at risk and the tumour, over up to three successive courses;
* normal-tissue complication probability under the Lyman probit model;
* radiation-induced cancer risk under a linear-exponential model.

Where the 2014 implementation is quirky, the quirk is reproduced and named. Two
switches in :class:`Options` select between bug-for-bug reproduction and the
corrected behaviour; both default to reproduction.

References
----------
Voyant C, Julian D, Roustit R, Biffi K, Lantieri C. Biological effects and
equivalent doses in radiotherapy: a software solution. *Rep Pract Oncol
Radiother* 2014;19(1):47-55.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .schedule import TimeModel, course_days, overall_time
from .tissues import Library, Tissue, load_library

#: Interval between the two daily fractions assumed by the incomplete-repair
#: correction, in hours. Hard-coded in the 2014 source.
BIFRACTION_INTERVAL_HOURS = 6.0

#: Tumour drop-down indices whose repopulation dose is tabulated rather than
#: derived from ``alpha`` and ``Tp``.
_FIXED_DPROL_TUMOURS = (6, 15)

#: The reference search grid of the 2014 application: fraction counts in
#: hundredths, from 0 to 100 for the organ at risk, -100 to 100 for the tumour.
_GRID_STEP = 0.01
_OAR_BOUNDS = (0.0, 100.0)
_TUMOUR_BOUNDS = (-100.0, 100.0)


class NotComputable(Exception):
    """Raised when the model does not apply to the requested schedule."""


@dataclass(frozen=True)
class Options:
    """Switches between 2014-compatible and corrected behaviour."""

    #: Snap the equivalent fraction count to the 2014 grid of 0.01 fractions.
    #: The underlying root is exact either way; this only quantises it.
    legacy_quantisation: bool = True
    #: Calendar model beyond 86 fractions. See :mod:`lqlequiv.schedule`.
    time_model: TimeModel = TimeModel.LEGACY
    #: Sigmoid used for the tumour control probability, which is new in 3.0.
    tcp_model: "TCPModel" = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.tcp_model is None:
            object.__setattr__(self, "tcp_model", TCPModel.LOGISTIC)


@dataclass(frozen=True)
class Course:
    """One course of treatment: a dose per fraction, repeated, after a gap."""

    dose_per_fraction: float
    n_fractions: float
    gap_days: float = 0.0

    @property
    def total_dose(self) -> float:
        return self.dose_per_fraction * self.n_fractions

    @property
    def is_empty(self) -> bool:
        return self.dose_per_fraction == 0.0 or self.n_fractions == 0.0


@dataclass(frozen=True)
class Prescription:
    """A reference fractionation plus up to three successive courses."""

    courses: tuple[Course, ...]
    reference_dose: float = 2.0
    bifractionated: bool = False

    def __post_init__(self) -> None:
        if len(self.courses) > 3:
            raise ValueError("at most three successive courses are supported")
        if self.reference_dose < 0:
            raise ValueError("reference dose must not be negative")
        for course in self.courses:
            if course.dose_per_fraction < 0 or course.n_fractions < 0 or course.gap_days < 0:
                raise ValueError("doses, fraction counts and gaps must not be negative")


@dataclass(frozen=True)
class CourseResult:
    """Per-course output."""

    bed_oar: float
    eqd_oar: float
    bed_tumour: float
    eqd_tumour: float
    overall_days_oar: float
    overall_days_tumour: float
    equivalent_fractions_oar: float
    equivalent_fractions_tumour: float


@dataclass(frozen=True)
class Result:
    """Full output of :func:`compute`."""

    courses: tuple[CourseResult, ...]
    eqd_oar_total: float
    eqd_tumour_total: float
    ntcp_percent: float | None
    tcp_percent: float | None
    cancer_risk: float | None
    #: False when two fractions a day are combined with a dose above the
    #: linear-quadratic-linear transition dose: the incomplete-repair correction
    #: is not defined there. The 2014 interface printed "NC" in that case.
    oar_total_valid: bool = True
    tumour_total_valid: bool = True
    endpoint: str = ""
    options: Options = field(default_factory=Options)

    @property
    def total_dose(self) -> float:
        return sum(c.bed_oar for c in self.courses)


def _heaviside(x: float) -> float:
    """Step function, zero at the origin -- the convention the 2014 code relies on."""
    return 1.0 if x > 0.0 else 0.0


def _incomplete_repair(tissue: Tissue) -> float:
    """Thames' ``Hm`` correction for two fractions a day, zero for one a day."""
    if tissue.T_half <= 0.0:
        return 0.0
    phi = math.exp(-0.693 * BIFRACTION_INTERVAL_HOURS / tissue.T_half)
    if phi >= 1.0:
        return 0.0
    return (phi / (1 - phi)) * (2 - (1 - phi**2) / (1 - phi))


def _quantise(value: float, bounds: tuple[float, float], options: Options) -> float:
    """Clamp to the search interval, and snap to the 2014 grid if asked.

    The 2014 code takes the ``min`` over a grid of hundredths of a fraction; on
    an exact tie MATLAB's ``min`` returns the first index, that is, the lower
    one. ``ceil(x - 0.5)`` reproduces that half-down rounding, including for
    negative fraction counts.
    """
    low, high = bounds
    if not options.legacy_quantisation:
        return min(max(value, low), high)
    index = math.ceil(value / _GRID_STEP - 0.5)
    index = min(max(index, round(low / _GRID_STEP)), round(high / _GRID_STEP))
    return index * _GRID_STEP


def _lql_dose_term(dose: float, tissue: Tissue, gamma: float, repair: float) -> float:
    """BED contribution of a single fraction, before repopulation.

    Below the transition dose this is the linear-quadratic form; above it, the
    linear tail of Astrahan. The incomplete-repair correction only applies to
    the quadratic branch, exactly as in the 2014 source.
    """
    if dose >= tissue.dt:
        return tissue.dt * (1 + tissue.dt / tissue.alpha_beta) + gamma * (dose - tissue.dt)
    return dose * (1 + (1 + repair) * dose / tissue.alpha_beta)


# --------------------------------------------------------------------------
# Organ at risk
# --------------------------------------------------------------------------


def _oar_course_bed(course: Course, tissue: Tissue, gamma: float, repair: float) -> float:
    """BED of one course for an organ at risk.

    The organ-at-risk branch of the 2014 code applies repopulation as a flat
    ``n * 7/5 * dprol``: it ignores both the kick-off time ``Tk`` and any gap.
    """
    per_fraction = _lql_dose_term(course.dose_per_fraction, tissue, gamma, repair)
    return course.n_fractions * per_fraction - course.n_fractions * (7.0 / 5.0) * tissue.dprol


def _oar_grid_residual(
    index: int, bed: float, reference_dose: float, tissue: Tissue, gamma: float
) -> float:
    """Objective of the 2014 grid search at one grid point.

    Evaluated in the same order as the MATLAB expression so that the comparison
    between neighbouring grid points comes out the same way, down to the last
    bit. That matters: when the exact root falls halfway between two grid
    points, which one the original ``min`` returns is decided by rounding noise.
    """
    n = index * _GRID_STEP
    elapsed = n * 7.0 / 5.0
    value = n * _lql_dose_term(reference_dose, tissue, gamma, 0.0) - elapsed * tissue.dprol
    return abs(bed - value)


def _oar_equivalent_fractions(
    bed: float, reference_dose: float, tissue: Tissue, gamma: float, options: Options
) -> float:
    """Number of reference fractions delivering the same BED.

    The organ-at-risk objective is strictly linear in the fraction count, so the
    root is closed-form. When the 2014 grid is being reproduced, the two grid
    points bracketing that root are scored against each other exactly as the
    original search would have, rather than simply rounded.
    """
    slope = _lql_dose_term(reference_dose, tissue, gamma, 0.0) - (7.0 / 5.0) * tissue.dprol
    if slope == 0.0:
        return 0.0
    root = bed / slope
    low, high = _OAR_BOUNDS
    if not options.legacy_quantisation:
        return min(max(root, low), high)

    lowest, highest = round(low / _GRID_STEP), round(high / _GRID_STEP)
    exact = root / _GRID_STEP
    candidates = {
        min(max(index, lowest), highest)
        for index in (math.floor(exact), math.ceil(exact), lowest, highest)
    }
    best = min(
        candidates,
        key=lambda index: (
            _oar_grid_residual(index, bed, reference_dose, tissue, gamma), index
        ),
    )
    return best * _GRID_STEP


# --------------------------------------------------------------------------
# Tumour
# --------------------------------------------------------------------------


def _tumour_dprol(tissue: Tissue) -> float:
    """Dose consumed per day by tumour repopulation, in Gy/day."""
    if tissue.index in _FIXED_DPROL_TUMOURS:
        return 0.3
    if tissue.alpha <= 0.0 or tissue.Tp <= 0.0:
        return 0.0
    return 0.693 / (tissue.alpha * tissue.Tp)


def _repopulation_loss(
    days_before: float, days_of_course: float, tissue: Tissue, dprol: float
) -> float:
    """Dose lost to repopulation during one course, given what preceded it."""
    already = (tissue.Tk - days_before) * _heaviside(tissue.Tk - days_before)
    return (
        _heaviside(days_before + days_of_course - tissue.Tk)
        * dprol
        * (days_of_course - already)
    )


def _tumour_course_bed(
    course: Course,
    days_before: float,
    days_of_course: float,
    tissue: Tissue,
    gamma: float,
    repair: float,
    dprol: float,
) -> float:
    per_fraction = _lql_dose_term(course.dose_per_fraction, tissue, gamma, repair)
    loss = _repopulation_loss(days_before, days_of_course, tissue, dprol)
    return course.n_fractions * per_fraction - loss


def _tumour_reference_bed(
    n: float, reference_dose: float, days_before: float, tissue: Tissue,
    gamma: float, dprol: float,
) -> float:
    """BED of ``n`` reference fractions delivered after ``days_before`` days."""
    days = n * 7.0 / 5.0
    per_fraction = _lql_dose_term(reference_dose, tissue, gamma, 0.0)
    return n * per_fraction - _repopulation_loss(days_before, days, tissue, dprol)


def _tumour_equivalent_fractions(
    bed: float, reference_dose: float, days_before: float, tissue: Tissue,
    gamma: float, dprol: float, options: Options,
) -> float:
    """Number of reference fractions matching ``bed`` for the tumour.

    Unlike the organ-at-risk objective, this one is only *piecewise* linear:
    repopulation switches on when the cumulative overall time crosses the
    kick-off time ``Tk``, putting a kink at ``n = (Tk - days_before) * 5/7``.
    Both branches are solved in closed form and the best candidate is kept,
    which reproduces what the 2014 grid search converges to, including when no
    root exists inside the search interval and the minimum sits on a bound.
    """
    slope = _lql_dose_term(reference_dose, tissue, gamma, 0.0)
    already = (tissue.Tk - days_before) * _heaviside(tissue.Tk - days_before)
    kink = (tissue.Tk - days_before) * 5.0 / 7.0
    low, high = _TUMOUR_BOUNDS

    roots: list[float] = [kink]
    # Before the kink no repopulation applies.
    if slope != 0.0:
        roots.append(bed / slope)
    # After it, the slope is reduced by the daily repopulation dose, so the
    # objective can cross the target a second time.
    tail_slope = slope - dprol * 7.0 / 5.0
    if tail_slope != 0.0:
        roots.append((bed - dprol * already) / tail_slope)

    if not options.legacy_quantisation:
        return min(
            (min(max(n, low), high) for n in roots),
            key=lambda n: abs(
                _tumour_reference_bed(n, reference_dose, days_before, tissue, gamma, dprol)
                - bed
            ),
        )

    lowest, highest = round(low / _GRID_STEP), round(high / _GRID_STEP)
    candidates = {lowest, highest}
    for root in roots:
        exact = root / _GRID_STEP
        # Repopulation switches on across the kink, so the objective is
        # discontinuous in slope there and the best grid point can be the
        # neighbour rather than the bracketing pair: widen by one either way.
        for offset in (-2, -1, 0, 1, 2):
            candidates.add(
                min(max(math.floor(exact) + offset, lowest), highest)
            )

    def residual(index: int) -> float:
        n = index * _GRID_STEP
        return abs(
            _tumour_reference_bed(n, reference_dose, days_before, tissue, gamma, dprol) - bed
        )

    best = min(candidates, key=lambda index: (residual(index), index))
    return best * _GRID_STEP


# --------------------------------------------------------------------------
# Toxicity endpoints
# --------------------------------------------------------------------------


def normal_tissue_complication_probability(eqd: float, tissue: Tissue) -> float | None:
    """Lyman probit complication probability, in percent.

    Returns ``None`` when the tissue has no tabulated Lyman parameters. The 2014
    application divided by zero in that case and reported 100 %.
    """
    if not tissue.has_ntcp:
        return None
    t = (eqd - tissue.d50) / (tissue.m * tissue.d50)
    probability = 0.5 * (1 + math.erf(t / math.sqrt(2))) * 100.0
    return 0.0 if probability < 0.1 else probability


class TCPModel(str, Enum):
    """Sigmoid used to turn (gamma50, TCD50) into a control probability.

    The 2014 library tabulates a normalised slope and a TCD50 for eleven tumour
    sites but never uses them, so it records no choice of sigmoid. Both of the
    standard parameterisations are offered here and the choice is reported with
    the result.
    """

    #: ``TCP = 1 / (1 + (TCD50/D) ** (4 * gamma50))``
    LOGISTIC = "logistic"
    #: ``TCP = 2 ** (-exp(e * gamma50 * (1 - D/TCD50)))``
    POISSON = "poisson"


def tumour_control_probability(
    eqd: float, tissue: Tissue, model: TCPModel = TCPModel.LOGISTIC
) -> float | None:
    """Tumour control probability at an equivalent dose ``eqd``, in percent.

    Returns ``None`` when the tumour has no tabulated dose-response parameters.

    Note that this is a *tumour* quantity and has nothing to do with
    :func:`normal_tissue_complication_probability`, which applies to healthy
    tissue only. New in 3.0: the 2014 application computed no tumour endpoint.
    """
    if not tissue.has_tcp:
        return None
    gamma50, tcd50 = tissue.gamma50, tissue.tcd50
    if eqd <= 0.0:
        return 0.0
    if model is TCPModel.LOGISTIC:
        probability = 1.0 / (1.0 + (tcd50 / eqd) ** (4.0 * gamma50))
    else:
        exponent = math.e * gamma50 * (1.0 - eqd / tcd50)
        # Guard the double exponential against overflow at low dose.
        probability = 0.0 if exponent > 700 else 2.0 ** (-math.exp(exponent))
    return probability * 100.0


def radiation_induced_cancer_risk(eqd: float, tissue: Tissue) -> float | None:
    """Linear-exponential radiation-induced cancer risk.

    Returns ``None`` when no risk coefficient is tabulated, which is what the
    2014 interface showed as a question mark.
    """
    if not tissue.has_cancer_risk:
        return None
    return tissue.puns * eqd * math.exp(-tissue.alpha2 * eqd)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def compute(
    organ: Tissue | str | int,
    tumour: Tissue | str | int,
    prescription: Prescription,
    options: Options | None = None,
    library: Library | None = None,
) -> Result:
    """Compute equivalent doses, complication probability and cancer risk.

    Parameters
    ----------
    organ, tumour:
        Either a :class:`~lqlequiv.tissues.Tissue`, or a name or 2014 drop-down
        index to look up in the library.
    prescription:
        The reference fractionation and the successive courses to convert.
    options:
        Reproduction switches; defaults to reproducing the 2014 behaviour.
    library:
        Radiobiological library, defaulting to the shipped one.

    Returns
    -------
    Result
        Per-course and cumulative equivalent doses, plus the toxicity endpoints.
    """
    options = options or Options()
    library = library or load_library()
    gamma = library.gamma_over_alpha
    oar = organ if isinstance(organ, Tissue) else library.organ(organ)
    tum = tumour if isinstance(tumour, Tissue) else library.tumour_site(tumour)

    repair_oar = _incomplete_repair(oar) if prescription.bifractionated else 0.0
    repair_tum = _incomplete_repair(tum) if prescription.bifractionated else 0.0
    dprol_tum = _tumour_dprol(tum)
    reference = prescription.reference_dose

    results: list[CourseResult] = []
    eqd_oar_running = 0.0
    eqd_tum_running = 0.0
    # Two distinct running times feed the tumour repopulation term, and they are
    # not interchangeable: the delivered course is scored against the calendar
    # time actually elapsed, whereas the reference schedule it is being matched
    # to is scored against the calendar time its own equivalent fractions span.
    elapsed_days = 0.0
    equivalent_days = 0.0

    for course in prescription.courses:
        empty = course.is_empty or reference == 0.0

        # --- organ at risk -------------------------------------------------
        bed_oar = _oar_course_bed(course, oar, gamma, repair_oar)
        if empty:
            n_oar = 0.0
            days_course = 0.0
            days_reference = 0.0
        else:
            n_oar = _oar_equivalent_fractions(bed_oar, reference, oar, gamma, options)
            days_course = course_days(
                course.n_fractions, course.gap_days,
                prescription.bifractionated, options.time_model,
            )
            days_reference = overall_time(n_oar, options.time_model)
        eqd_oar = n_oar * reference - (days_course - days_reference) * oar.dprol
        # The 2014 code clamps the *cumulative* organ-at-risk dose at zero.
        if eqd_oar + eqd_oar_running < 0.0:
            eqd_oar = -eqd_oar_running

        # --- tumour --------------------------------------------------------
        # An empty course still spans calendar time, and the 2014 code scores its
        # repopulation loss into the reported BED; only the equivalent dose and
        # the time carried into the next course are forced back to zero.
        days_tum_course = (course.n_fractions + course.gap_days) * 7.0 / 5.0
        bed_tum = _tumour_course_bed(
            course, elapsed_days, days_tum_course, tum, gamma, repair_tum, dprol_tum
        )
        if empty:
            n_tum = 0.0
        else:
            n_tum = _tumour_equivalent_fractions(
                bed_tum, reference, equivalent_days, tum, gamma, dprol_tum, options
            )
        eqd_tum = n_tum * reference
        if eqd_tum + eqd_tum_running < 0.0:
            eqd_tum = -eqd_tum_running
        # A negative equivalent fraction count contributes no elapsed time.
        equivalent_days += max(n_tum, 0.0) * 7.0 / 5.0
        elapsed_days += 0.0 if empty else days_tum_course

        eqd_oar_running += eqd_oar
        eqd_tum_running += eqd_tum
        results.append(
            CourseResult(
                bed_oar=bed_oar, eqd_oar=eqd_oar,
                bed_tumour=bed_tum, eqd_tumour=eqd_tum,
                overall_days_oar=days_course, overall_days_tumour=days_tum_course,
                equivalent_fractions_oar=n_oar, equivalent_fractions_tumour=n_tum,
            )
        )

    # Two fractions a day are incompatible with the linear tail: the
    # incomplete-repair correction is only defined on the quadratic branch.
    oar_valid = not (
        prescription.bifractionated
        and any(c.dose_per_fraction > oar.dt for c in prescription.courses)
    )
    tumour_valid = not (
        prescription.bifractionated
        and any(c.dose_per_fraction > tum.dt for c in prescription.courses)
    )

    return Result(
        courses=tuple(results),
        eqd_oar_total=eqd_oar_running,
        eqd_tumour_total=eqd_tum_running,
        ntcp_percent=normal_tissue_complication_probability(eqd_oar_running, oar),
        tcp_percent=tumour_control_probability(eqd_tum_running, tum, options.tcp_model),
        cancer_risk=radiation_induced_cancer_risk(eqd_oar_running, oar),
        oar_total_valid=oar_valid,
        tumour_total_valid=tumour_valid,
        endpoint=oar.endpoint,
        options=options,
    )


__all__ = [
    "Course", "CourseResult", "NotComputable", "Options", "Prescription",
    "Result", "TCPModel", "TimeModel", "compute",
    "normal_tissue_complication_probability", "radiation_induced_cancer_risk",
    "tumour_control_probability",
]
