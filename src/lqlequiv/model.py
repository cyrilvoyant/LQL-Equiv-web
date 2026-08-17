"""Biologically equivalent doses under the linear-quadratic-linear model.

The calculation performed by ``pushbutton4_Callback`` in the 2014 MATLAB
application (``cyrilvoyant/LQ-Equiv``), covering:

* biologically effective dose (BED) with the linear-quadratic-linear tail of
  Astrahan, the proliferation term of Dale, and the incomplete-repair correction
  of Thames for two fractions a day;
* the equivalent dose in a reference fractionation (EQD, usually EQD2), for both
  the organ at risk and the tumour, over any number of successive courses;
* normal-tissue complication probability under the Lyman probit model;
* radiation-induced cancer risk under a linear-exponential model.

The equations solved here are the ones published alongside that application,
which is not quite the same thing as the code it shipped: three calendar
conventions in the 2014 source are not described by its own equations, and the
largest of them adds a second proliferation term to the reported organ dose.
Those conventions are named in :class:`Options` and measured in
``docs/COMPARISON-2014.md``. :meth:`Options.legacy_2014` reproduces them, for
anyone recomputing a result published before 2026 and for the non-regression
suite; nothing else does.

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

from .schedule import TimeModel, course_days, overall_time, staircase_segments
from .tissues import Library, Tissue, load_library

#: Interval between the two daily fractions assumed by the incomplete-repair
#: correction, in hours. Hard-coded in the 2014 source.
BIFRACTION_INTERVAL_HOURS = 6.0

#: Tumour drop-down indices whose proliferation dose is tabulated rather than
#: derived from ``alpha`` and ``Tp``.
_FIXED_DPROL_TUMOURS = (6, 15)

#: The reference search grid of the 2014 application: fraction counts in
#: hundredths, from 0 to 100 for the organ at risk, -100 to 100 for the tumour.
#: A schedule whose equivalent exceeds 100 reference fractions is reported *at*
#: the bound by the original software, silently: the answer stops moving.
_GRID_STEP = 0.01
_OAR_BOUNDS = (0.0, 100.0)
_TUMOUR_BOUNDS = (-100.0, 100.0)

#: Those bounds existed only because the 2014 code scanned a finite grid. With
#: the root solved in closed form there is no such constraint, so exact mode
#: widens them tenfold and the answer keeps moving.
_EXACT_OAR_BOUNDS = (0.0, 1000.0)
_EXACT_TUMOUR_BOUNDS = (-1000.0, 1000.0)


class NotComputable(Exception):
    """Raised when the model does not apply to the requested schedule."""


@dataclass(frozen=True)
class Options:
    """How to compute. The defaults are the behaviour the software stands behind.

    ``Options()`` solves the published equations. Nothing here needs setting for
    ordinary use; the fields exist so that the validation suite can reproduce the
    2014 application, through :meth:`legacy_2014`.
    """

    #: Snap the equivalent fraction count to the 2014 grid of 0.01 fractions.
    #: The underlying root is exact either way; this only quantises it.
    legacy_quantisation: bool = False
    #: Calendar model beyond 86 fractions. See :mod:`lqlequiv.schedule`.
    time_model: TimeModel = TimeModel.STAIRCASE
    #: Sigmoid used for the tumour control probability, which is new in 3.0.
    tcp_model: TCPModel = None  # type: ignore[assignment]
    #: Reproduce the three calendar conventions the 2014 source imposed and its
    #: published equations did not describe:
    #:
    #: * the organ-at-risk proliferation loss is a flat ``n * 7/5 * dprol``, so
    #:   the kick-off time ``Tk`` is never read for an organ, though it is for a
    #:   tumour;
    #: * the reported organ equivalent dose is
    #:   ``n_r * d_r - (T_course - T_reference) * dprol``, a calendar correction
    #:   applied on top of a root that already balanced proliferation;
    #: * the tumour calendar is a flat ``(n + g) * 7/5``, blind to the weekend
    #:   staircase and to two fractions a day.
    #:
    #: The second is the consequential one: nil at the reference fraction size,
    #: where the two calendars coincide, and growing with the departure from it.
    #: ``docs/COMPARISON-2014.md`` measures it and gives the round-trip criterion
    #: that separates the two.
    reproduce_2014: bool = False

    def __post_init__(self) -> None:
        if self.tcp_model is None:
            object.__setattr__(self, "tcp_model", TCPModel.LOGISTIC)

    @classmethod
    def legacy_2014(cls, tcp_model: TCPModel | None = None) -> "Options":
        """Reproduce the 2014 MATLAB application, quirks and calendars included.

        For recomputing a result published before 2026, and for the
        non-regression suite. Not for new work.
        """
        return cls(legacy_quantisation=True, time_model=TimeModel.LEGACY,
                   tcp_model=tcp_model, reproduce_2014=True)


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


#: The 2014 interface had exactly three course slots. Nothing in the model
#: depends on that number -- courses accumulate through a loop -- so the limit
#: here is only a guard against absurd input. Schedules of one to three courses
#: behave exactly as the 2014 application; beyond that the same rules simply
#: keep applying.
MAX_COURSES = 10


@dataclass(frozen=True)
class Prescription:
    """A reference fractionation plus a sequence of successive courses."""

    courses: tuple[Course, ...]
    reference_dose: float = 2.0
    bifractionated: bool = False

    def __post_init__(self) -> None:
        if len(self.courses) > MAX_COURSES:
            raise ValueError(f"at most {MAX_COURSES} successive courses are supported")
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
    #: True when the equivalent fraction count ran into the end of the search
    #: interval, so the answer is the bound rather than a solution. The 2014
    #: application reported the bound with no indication that it had done so.
    oar_saturated: bool = False
    tumour_saturated: bool = False


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

    @property
    def saturated(self) -> bool:
        """Whether any equivalent dose is a search bound rather than a solution.

        Beyond roughly a hundred reference fractions the 2014 search interval
        runs out and the equivalent dose stops responding to the schedule. Such
        a value must not be read as a result.
        """
        return any(c.oar_saturated or c.tumour_saturated for c in self.courses)


def _at_bound(value: float, bounds: tuple[float, float]) -> bool:
    """Whether a solved fraction count is sitting on the end of the interval."""
    low, high = bounds
    return abs(value - low) < _GRID_STEP or abs(value - high) < _GRID_STEP


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


def _lql_dose_term(dose: float, tissue: Tissue, gamma: float, repair: float) -> float:
    """BED contribution of a single fraction, before proliferation.

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

    The organ-at-risk branch of the 2014 code applies proliferation as a flat
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
    if not options.legacy_quantisation:
        low, high = _EXACT_OAR_BOUNDS
        return min(max(root, low), high)
    low, high = _OAR_BOUNDS

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
    """Dose consumed per day by tumour proliferation, in Gy/day.

    Normally derived from the doubling time, but tabulated for the two sites the
    2014 source special-cased and for any entry that declares it explicitly --
    including one that declares no proliferation at all.
    """
    if tissue.dprol_override is not None:
        return tissue.dprol_override
    if tissue.alpha <= 0.0 or tissue.Tp <= 0.0:
        return 0.0
    return 0.693 / (tissue.alpha * tissue.Tp)


def _proliferation_loss(
    days_before: float, days_of_course: float, tissue: Tissue, dprol: float
) -> float:
    """Dose lost to proliferation during one course, given what preceded it."""
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
    loss = _proliferation_loss(days_before, days_of_course, tissue, dprol)
    return course.n_fractions * per_fraction - loss


def _tumour_reference_bed(
    n: float, reference_dose: float, days_before: float, tissue: Tissue,
    gamma: float, dprol: float,
) -> float:
    """BED of ``n`` reference fractions delivered after ``days_before`` days."""
    days = n * 7.0 / 5.0
    per_fraction = _lql_dose_term(reference_dose, tissue, gamma, 0.0)
    return n * per_fraction - _proliferation_loss(days_before, days, tissue, dprol)


def _tumour_equivalent_fractions(
    bed: float, reference_dose: float, days_before: float, tissue: Tissue,
    gamma: float, dprol: float, options: Options,
) -> float:
    """Number of reference fractions matching ``bed`` for the tumour.

    Unlike the organ-at-risk objective, this one is only *piecewise* linear:
    proliferation switches on when the cumulative overall time crosses the
    kick-off time ``Tk``, putting a kink at ``n = (Tk - days_before) * 5/7``.
    Both branches are solved in closed form and the best candidate is kept,
    which reproduces what the 2014 grid search converges to, including when no
    root exists inside the search interval and the minimum sits on a bound.
    """
    slope = _lql_dose_term(reference_dose, tissue, gamma, 0.0)
    already = (tissue.Tk - days_before) * _heaviside(tissue.Tk - days_before)
    kink = (tissue.Tk - days_before) * 5.0 / 7.0
    low, high = (_TUMOUR_BOUNDS if options.legacy_quantisation
                 else _EXACT_TUMOUR_BOUNDS)

    roots: list[float] = [kink]
    # Before the kink no proliferation applies.
    if slope != 0.0:
        roots.append(bed / slope)
    # After it, the slope is reduced by the daily proliferation dose, so the
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
        # Proliferation switches on across the kink, so the objective is
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

    if not options.reproduce_2014:
        return _compute_adjusted(oar, tum, prescription, options, library, gamma)

    oar_bounds = _OAR_BOUNDS if options.legacy_quantisation else _EXACT_OAR_BOUNDS
    tumour_bounds = (_TUMOUR_BOUNDS if options.legacy_quantisation
                     else _EXACT_TUMOUR_BOUNDS)
    repair_oar = _incomplete_repair(oar) if prescription.bifractionated else 0.0
    repair_tum = _incomplete_repair(tum) if prescription.bifractionated else 0.0
    dprol_tum = _tumour_dprol(tum)
    reference = prescription.reference_dose

    results: list[CourseResult] = []
    eqd_oar_running = 0.0
    eqd_tum_running = 0.0
    # Two distinct running times feed the tumour proliferation term, and they are
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
        # proliferation loss into the reported BED; only the equivalent dose and
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
                # An empty course sits at zero by construction, not by saturation.
                oar_saturated=not empty and _at_bound(n_oar, oar_bounds),
                tumour_saturated=not empty and _at_bound(n_tum, tumour_bounds),
            )
        )

    # Two fractions a day are incompatible with the linear tail: the
    # incomplete-repair correction is only defined on the quadratic branch.
    oar_valid = not (
        prescription.bifractionated
        and any(c.dose_per_fraction >= oar.dt for c in prescription.courses)
    )
    tumour_valid = not (
        prescription.bifractionated
        and any(c.dose_per_fraction >= tum.dt for c in prescription.courses)
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


def _sessions(course: Course, bifractionated: bool) -> float:
    """Treatment days a course occupies, gap included, before weekends.

    Two fractions a day occupy half as many days, rounded up: eleven fractions
    delivered twice a day need six days, not five and a half.
    """
    if not bifractionated:
        delivered = course.n_fractions
    else:
        delivered = math.ceil(course.n_fractions / 2.0)
    return delivered + course.gap_days


def _time_loss(
    days_before: float, span: float, tissue: Tissue, dprol: float, kick_off: bool
) -> float:
    """Dose lost to proliferation over one course, in gray.

    Two models, as the 2014 paper sets them out. The target volume follows Dale:
    nothing is lost until the overall time passes the kick-off time ``Tk``,
    equations (3) and (4). The organ at risk follows Van Dyk: there is no kick-off
    time, and the recovered dose accrues from the first day, equations (6) and (7).
    The paper is explicit that the two differ -- "for the organs at risk, the
    kick-off time is not relevant" -- and the difference is not an oversight.
    """
    if not kick_off:
        return dprol * span
    return _proliferation_loss(days_before, span, tissue, dprol)


def _reference_fractions(
    bed: float, reference_dose: float, sessions_before: float, tissue: Tissue,
    gamma: float, dprol: float, model: TimeModel, kick_off: bool,
) -> float:
    """Reference fractions matching ``bed``, on the real weekend calendar.

    Proliferation is charged per elapsed calendar day, weekends included, so the
    reference schedule spans ``overall_time(n)`` days and not ``7n/5``. That
    makes the equality a step function in ``n``, with no closed form over the
    whole range. It has one on each segment between two weekends, where the
    staircase is exactly ``n + offset``: the loss is then linear in ``n``, on
    each side of the kick-off time, and the root follows. Every segment is
    solved, the roots that fall outside their own segment are discarded, and the
    survivor with the smallest residual is kept -- which also covers the case
    where the target falls in one of the two-day gaps the staircase jumps over.
    """
    per_fraction = _lql_dose_term(reference_dose, tissue, gamma, 0.0)
    best, best_residual = 0.0, math.inf

    def residual(n: float) -> float:
        days_before = overall_time(sessions_before, model)
        span = overall_time(sessions_before + n, model) - days_before
        return abs(
            n * per_fraction
            - _time_loss(days_before, span, tissue, dprol, kick_off)
            - bed
        )

    low_bound, high_bound = _EXACT_TUMOUR_BOUNDS
    days_before = overall_time(sessions_before, model)
    already = ((tissue.Tk - days_before) * _heaviside(tissue.Tk - days_before)
               if kick_off else 0.0)
    tail_slope = per_fraction - dprol

    # The scan must reach the search bound, not some closer round number. An
    # earlier version stopped 400 sessions ahead, which silently clamped the
    # answer at 401 reference fractions and reported it as a solution -- the same
    # failure the 2014 bound of 100 produced, and no more acceptable here.
    for low, high, offset in staircase_segments(sessions_before + high_bound):
        # The segments are cut on the staircase argument, which is the running
        # session count, so the interval on n is shifted by what came before.
        low_n = max(low - sessions_before, low_bound)
        high_n = min(high - sessions_before, high_bound)
        if high_n < low_n:
            continue
        # With a kick-off time there is a branch below it where nothing is lost;
        # without one the loss applies throughout. Either way it is affine in n
        # on this segment, so the root is closed-form.
        candidates = []
        if kick_off:
            candidates.append(bed / per_fraction if per_fraction else 0.0)
        if tail_slope:
            constant = dprol * (sessions_before + offset - days_before - already)
            candidates.append((bed + constant) / tail_slope)
        # The boundaries too, for a target that falls inside one of the jumps.
        candidates.extend((low_n, high_n))
        for root in candidates:
            n = min(max(root, low_n), high_n)
            value = residual(n)
            # The staircase drops the reference BED by two days' worth of
            # proliferation at every weekend, so a target can be met by two
            # different fraction counts, one on each side of a jump. Both are
            # exact; the shorter is reported, so that the answer is a function.
            if value < best_residual - 1e-9 or (
                abs(value - best_residual) <= 1e-9 and n < best
            ):
                best, best_residual = n, value

    return best


def _compute_adjusted(
    oar: Tissue, tum: Tissue, prescription: Prescription, options: Options,
    library: Library, gamma: float,
) -> Result:
    """Solve the published equations rather than reproduce the 2014 source.

    Three things differ from ``Options.legacy_2014()``, and each of them is a
    place where the 2014 code and the equations it was published with disagree.

    Delivered and reference schedules run on one absolute calendar, the real one:
    treatment five days a week, so ``n`` sessions span ``overall_time(n)`` days,
    weekends included. Proliferation is charged per elapsed day, so it must be
    the real calendar and not its ``7n/5`` long-run rate, which overstates the
    span by up to two days. Both sides of the equality use it, or the two losses
    fail to cancel when the evaluated schedule *is* the reference schedule and 39
    fractions of 2 Gy stop returning 78 Gy.

    Sessions accumulate across courses rather than restarting, so forty fractions
    in one course and twenty plus twenty span the same time, and a gap is counted
    in missed sessions so that the weekends inside it are supplied by the
    staircase itself. The two tissues keep the two proliferation models the paper
    gives them, Dale with a kick-off time for the target and Van Dyk without one
    for the organ, and the equivalent dose is the fraction count times the
    reference dose, with nothing added afterwards.
    """
    repair_oar = _incomplete_repair(oar) if prescription.bifractionated else 0.0
    repair_tum = _incomplete_repair(tum) if prescription.bifractionated else 0.0
    dprol = {"oar": oar.dprol, "tum": _tumour_dprol(tum)}
    #: Equations (3) and (4) of the 2014 paper carry the kick-off time; equations
    #: (6) and (7), for the organ at risk, deliberately do not.
    kick_off = {"oar": False, "tum": True}
    reference = prescription.reference_dose
    bounds = _EXACT_TUMOUR_BOUNDS
    model = options.time_model

    results: list[CourseResult] = []
    totals = {"oar": 0.0, "tum": 0.0}
    reference_sessions = {"oar": 0.0, "tum": 0.0}
    sessions_before = 0.0

    for course in prescription.courses:
        empty = course.is_empty or reference == 0.0
        sessions_after = sessions_before + _sessions(course, prescription.bifractionated)
        delivered_before = overall_time(sessions_before, model)
        days_of_course = overall_time(sessions_after, model) - delivered_before

        per_course: dict[str, tuple[float, float]] = {}
        for key, tissue, repair in (("oar", oar, repair_oar), ("tum", tum, repair_tum)):
            bed = (course.n_fractions
                   * _lql_dose_term(course.dose_per_fraction, tissue, gamma, repair)
                   - _time_loss(delivered_before, days_of_course, tissue,
                                dprol[key], kick_off[key]))
            if empty:
                fractions = 0.0
            else:
                fractions = _reference_fractions(
                    bed, reference, reference_sessions[key], tissue, gamma,
                    dprol[key], model, kick_off[key],
                )
            eqd = fractions * reference
            if eqd + totals[key] < 0.0:
                eqd = -totals[key]
            totals[key] += eqd
            reference_sessions[key] += max(fractions, 0.0)
            per_course[key] = (bed, fractions)

        sessions_before = sessions_after
        results.append(
            CourseResult(
                bed_oar=per_course["oar"][0], eqd_oar=per_course["oar"][1] * reference,
                bed_tumour=per_course["tum"][0],
                eqd_tumour=per_course["tum"][1] * reference,
                overall_days_oar=days_of_course, overall_days_tumour=days_of_course,
                equivalent_fractions_oar=per_course["oar"][1],
                equivalent_fractions_tumour=per_course["tum"][1],
                oar_saturated=not empty and _at_bound(per_course["oar"][1], bounds),
                tumour_saturated=not empty and _at_bound(per_course["tum"][1], bounds),
            )
        )

    valid = {
        key: not (prescription.bifractionated
                  and any(c.dose_per_fraction >= tissue.dt for c in prescription.courses))
        for key, tissue in (("oar", oar), ("tum", tum))
    }
    return Result(
        courses=tuple(results),
        eqd_oar_total=totals["oar"],
        eqd_tumour_total=totals["tum"],
        ntcp_percent=normal_tissue_complication_probability(totals["oar"], oar),
        tcp_percent=tumour_control_probability(totals["tum"], tum, options.tcp_model),
        cancer_risk=radiation_induced_cancer_risk(totals["oar"], oar),
        oar_total_valid=valid["oar"],
        tumour_total_valid=valid["tum"],
        endpoint=oar.endpoint,
        options=options,
    )


__all__ = [
    "Course", "CourseResult", "NotComputable", "Options",
    "Prescription", "Result", "TCPModel", "TimeModel", "compute",
    "normal_tissue_complication_probability", "radiation_induced_cancer_risk",
    "tumour_control_probability",
]
