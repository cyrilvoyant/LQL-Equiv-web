"""Checks against closed-form results, independent of the 2014 implementation.

Agreement with the reference implementation proves that the port is faithful.
It does not prove that either is right. These tests assert properties that
follow from the equations themselves: continuity where the model changes branch,
the behaviour of the proliferation term at its kick-off, and identities that can
be verified by hand.
"""

from __future__ import annotations

import math

import pytest

from lqlequiv import Course, Options, Prescription, compute, load_library
from lqlequiv.model import (BIFRACTION_INTERVAL_HOURS, _incomplete_repair,
                            _lql_dose_term, _tumour_dprol)
from lqlequiv.schedule import TimeModel, overall_time

#: What the software computes, and what every test below asserts unless it is
#: explicitly contrasting the two.
ADJUSTED = Options()
#: The 2014 application, reproduced. Present only so that the difference between
#: the two time conventions can be pinned rather than described.
LEGACY = Options.legacy_2014()


@pytest.fixture(scope="module")
def library():
    return load_library()


def test_lql_is_continuous_at_the_transition_dose(library):
    """The quadratic branch and the linear tail must meet at ``dt``.

    Below the transition the per-fraction term is d(1 + d/(alpha/beta)); above it
    the tail starts from that same value. A discontinuity here would put a step
    into every equivalent dose computed for stereotactic fraction sizes.
    """
    gamma = library.gamma_over_alpha
    for tissue in library.oar + library.tumour:
        below = _lql_dose_term(tissue.dt - 1e-9, tissue, gamma, 0.0)
        at = _lql_dose_term(tissue.dt, tissue, gamma, 0.0)
        assert below == pytest.approx(at, abs=1e-6), tissue.name


def test_linear_tail_has_the_declared_slope(library):
    """Above the transition, one extra gray of fraction dose adds gamma/alpha."""
    gamma = library.gamma_over_alpha
    tissue = library.organ("Rectum")
    step = (_lql_dose_term(tissue.dt + 2.0, tissue, gamma, 0.0)
            - _lql_dose_term(tissue.dt + 1.0, tissue, gamma, 0.0))
    assert step == pytest.approx(gamma)


def test_bed_matches_a_hand_calculation(library):
    """A schedule below the transition dose, computed by hand.

    Head and neck parameterised as in the standardisation study: alpha/beta = 10,
    alpha = 0.3, Tk = 21 d, Tp = 4 d, so Dprol = ln2/(alpha*Tp) = 0.5775 Gy/d.
    For 35 x 2 Gy the closed form gives 70(1 + 2/10) - 0.5775 (T - 21).
    """
    from dataclasses import replace

    tissue = replace(library.tumour_site("Larynx"), alpha_beta=10.0, dt=20.0,
                     alpha=0.3, Tk=21.0, Tp=4.0)
    dprol = _tumour_dprol(tissue)
    # The 2014 source writes the constant as 0.693 rather than ln 2, which biases
    # the proliferation dose by 2e-4 in relative terms. Pinned, not ADJUSTED:
    # changing it would move every historical result by that amount.
    assert dprol == pytest.approx(0.693 / (0.3 * 4.0), rel=1e-12)
    assert dprol != pytest.approx(math.log(2) / (0.3 * 4.0), rel=1e-6)
    assert dprol == pytest.approx(math.log(2) / (0.3 * 4.0), rel=1e-3)

    # The tumour branch converts fractions to days as a plain 7/5 ratio, not
    # through the staircase the organ-at-risk branch uses. See test below.
    time = 35 * 7 / 5
    expected = 70.0 * (1 + 2.0 / 10.0) - dprol * (time - 21.0)

    result = compute(library.organ("Spinal cord"), tissue,
                     Prescription(courses=(Course(2.0, 35),), reference_dose=2.0),
                     LEGACY, library)
    assert result.courses[0].bed_tumour == pytest.approx(expected, rel=1e-9)


def test_no_proliferation_loss_before_the_kick_off_time(library):
    """Below ``Tk`` the term is switched off, and switches on continuously."""
    tumour = library.tumour_site("Standard tumour")
    organ = library.organ("Spinal cord")
    dprol = _tumour_dprol(tumour)

    short = compute(organ, tumour,
                    Prescription(courses=(Course(2.0, 10),), reference_dose=2.0),
                    LEGACY, library)
    assert 10 * 7 / 5 < tumour.Tk
    assert short.courses[0].bed_tumour == pytest.approx(
        10 * 2.0 * (1 + 2.0 / tumour.alpha_beta), rel=1e-9)

    # Just past the kick-off the loss equals dprol times the excess time.
    for count in (16, 17):
        time = count * 7 / 5
        result = compute(organ, tumour,
                         Prescription(courses=(Course(2.0, count),), reference_dose=2.0),
                         LEGACY, library)
        expected = count * 2.0 * (1 + 2.0 / tumour.alpha_beta) - dprol * max(
            0.0, time - tumour.Tk)
        assert result.courses[0].bed_tumour == pytest.approx(expected, rel=1e-9)


def test_reference_schedule_is_its_own_equivalent_exactly(library):
    """At the reference fraction size the equality is satisfied at n_r = n.

    Both sides then span the same time and lose the same dose, so the equivalent
    dose is the physical dose whatever the parameters. This is the identity that
    distinguishes this convention from one correcting a single side.
    """
    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")
    for dose in (1.8, 2.0, 2.5):
        for count in (10, 25, 40):
            result = compute(organ, tumour,
                             Prescription(courses=(Course(dose, count),),
                                          reference_dose=dose), LEGACY, library)
            assert result.eqd_tumour_total == pytest.approx(dose * count, rel=1e-9)
            assert result.eqd_oar_total == pytest.approx(dose * count, rel=1e-9)


def test_incomplete_repair_vanishes_for_instant_repair(library):
    """As the repair half-time tends to zero, ``Hm`` must tend to zero."""
    from dataclasses import replace

    tissue = library.organ("Rectum")
    values = [_incomplete_repair(replace(tissue, T_half=h))
              for h in (2.0, 1.0, 0.5, 0.1, 0.01)]
    assert all(b < a for a, b in zip(values, values[1:]))
    assert values[-1] == pytest.approx(0.0, abs=1e-6)


def test_incomplete_repair_is_phi_for_two_fractions_a_day(library):
    """Thames's general form collapses to a single exponential at m = 2.

    For m fractions a day the correction is (2*phi/m)/(1-phi) * [m - (1-phi^m)/(1-phi)].
    At m = 2 the bracket is 2 - (1 + phi) = 1 - phi, so the whole expression is
    exactly phi. The manuscript prints the collapsed form; this pins that the
    code evaluates it and not something else.

    The decay constant is the rounded 0.693 the 2014 release used, not ln 2. The
    difference reaches 0.4 % of phi at the shortest repair half-time in the
    library, and it is preserved deliberately, as it is for Dprol.
    """
    from dataclasses import replace

    for half_time in (0.25, 0.5, 0.8, 1.5, 3.0, 5.0):
        tissue = replace(library.organ("Rectum"), T_half=half_time)
        phi = math.exp(-0.693 * BIFRACTION_INTERVAL_HOURS / half_time)
        assert _incomplete_repair(tissue) == pytest.approx(phi, rel=1e-12)
        assert phi != pytest.approx(
            2.0 ** (-BIFRACTION_INTERVAL_HOURS / half_time), rel=1e-6)
        # And the general form it comes from, evaluated independently here.
        general = ((2 * phi / 2) / (1 - phi)) * (2 - (1 - phi ** 2) / (1 - phi))
        assert general == pytest.approx(phi, rel=1e-12)


def _totals(library, courses, options, bifractionated=False,
            organ="Rectum", tumour="Prostate"):
    plan = Prescription(courses=courses, reference_dose=2.0,
                        bifractionated=bifractionated)
    result = compute(library.organ(organ), library.tumour_site(tumour), plan,
                     options, library)
    return result.eqd_oar_total, result.eqd_tumour_total


def test_adjusted_equivalent_dose_is_fractions_times_reference_dose(library):
    """EQD = n_r * d_r, with nothing added afterwards.

    The 2014 organ-at-risk branch reports n_r * d_r - (T_course - T_ref) * dprol,
    a second time correction laid on top of a root that already carried one. That
    is the behaviour LEGACY reproduces and it is not what the equations say. Under
    ADJUSTED the reported dose is the fraction count times the reference dose,
    which is the identity every downstream reading depends on.
    """
    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")
    for dose, count in ((3.0, 20), (1.8, 30), (6.0, 5), (2.0, 39)):
        plan = Prescription(courses=(Course(dose, count),), reference_dose=2.0)
        result = compute(organ, tumour, plan, ADJUSTED, library)
        for course in result.courses:
            assert course.eqd_oar == pytest.approx(
                course.equivalent_fractions_oar * 2.0, rel=1e-12)
            assert course.eqd_tumour == pytest.approx(
                course.equivalent_fractions_tumour * 2.0, rel=1e-12)

    # And the legacy convention deliberately does not satisfy it.
    plan = Prescription(courses=(Course(3.0, 20),), reference_dose=2.0)
    legacy = compute(organ, tumour, plan, LEGACY, library).courses[0]
    assert legacy.eqd_oar != pytest.approx(
        legacy.equivalent_fractions_oar * 2.0, rel=1e-6)


def test_adjusted_organ_dose_responds_to_the_kick_off_time(library):
    """Tk must enter the organ-at-risk calculation.

    The 2014 organ branch applies proliferation as a flat n * 7/5 * dprol and
    never reads Tk, so an organ that starts proliferating on day 100 is charged
    as though it started on day one.
    """
    from dataclasses import replace

    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")
    plan = Prescription(courses=(Course(3.0, 20),), reference_dose=2.0)

    def dose(options, kick_off):
        return compute(replace(organ, Tk=kick_off), tumour, plan, options,
                       library).eqd_oar_total

    assert dose(ADJUSTED, 100.0) != pytest.approx(dose(ADJUSTED, 28.0), rel=1e-6)
    assert dose(LEGACY, 100.0) == pytest.approx(dose(LEGACY, 28.0), rel=1e-15)


def test_adjusted_totals_do_not_depend_on_how_a_course_is_split(library):
    """Splitting a schedule into segments must not change the answer.

    This is not automatic. The equality is piecewise linear in the reference
    fraction count and the inverse of a nonlinear map is not additive, so it holds
    only because both schedules advance on one absolute calendar at the same rate
    and the reference is continued rather than restarted. The legacy convention
    restarts the weekend staircase at every course, and since Theta(40) = 54 while
    2 * Theta(20) = 52, two days of proliferation appear from nowhere.

    Tested away from the reference dose: at d = d_r the identity is trivial and an
    earlier version of this test passed while the property was broken.
    """
    whole = _totals(library, (Course(3.0, 40),), ADJUSTED)
    for split in ((Course(3.0, 20), Course(3.0, 20)),
                  tuple(Course(3.0, 10) for _ in range(4)),
                  (Course(3.0, 5), Course(3.0, 15), Course(3.0, 20))):
        assert _totals(library, split, ADJUSTED) == pytest.approx(whole, rel=1e-12)

    # Mixed fraction sizes, where the kick-off falls inside the second course.
    mixed = _totals(library, (Course(2.0, 20), Course(3.0, 10)), ADJUSTED)
    assert _totals(library, (Course(2.0, 10), Course(2.0, 10), Course(3.0, 10)),
                   ADJUSTED) == pytest.approx(mixed, rel=1e-12)

    # Under the 2014 convention the same split moves the total, because the
    # weekend staircase restarts at every course and Theta(40) = 54 against
    # 2 * Theta(20) = 52. Pinned so that the size of the difference is on record.
    legacy_whole = _totals(library, (Course(3.0, 40),), LEGACY)
    legacy_split = _totals(library, (Course(3.0, 20), Course(3.0, 20)), LEGACY)
    assert legacy_split[0] - legacy_whole[0] == pytest.approx(0.623, abs=1e-3)


def test_overall_time_is_the_real_calendar(library):
    """The reported span is elapsed calendar days, weekends and gaps included.

    Proliferation is charged per elapsed day, and cells do not rest at the
    weekend, so the span that enters the equality has to be the real one. Forty
    sessions run Monday to Friday span 54 days, not the 56 that the long-run rate
    7n/5 would give. Two fractions a day halve the sessions, hence the days.
    """
    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")

    def days(options, bifractionated, count=40, gap=0.0):
        plan = Prescription(courses=(Course(2.5, count, gap),), reference_dose=2.0,
                            bifractionated=bifractionated)
        course = compute(organ, tumour, plan, options, library).courses[0]
        return course.overall_days_oar, course.overall_days_tumour

    assert days(ADJUSTED, False) == pytest.approx(
        (overall_time(40, TimeModel.STAIRCASE),) * 2)
    assert days(ADJUSTED, True) == pytest.approx(
        (overall_time(20, TimeModel.STAIRCASE),) * 2)
    assert days(ADJUSTED, False)[0] == 54.0
    assert days(ADJUSTED, True)[0] == 26.0

    # A gap is counted in missed sessions, so the weekends inside it are supplied
    # by the staircase like any other: ten missed sessions add fourteen days.
    assert days(ADJUSTED, False, gap=10.0)[0] - days(ADJUSTED, False)[0] == 14.0

    # The 2014 tumour branch saw neither, computing (n + g) * 7/5 throughout.
    assert days(LEGACY, True)[1] == pytest.approx(56.0)

    # An odd count needs the extra half day rounded up: eleven fractions, six
    # sessions, and six sessions span six days since no weekend has fallen yet.
    assert days(ADJUSTED, True, count=11)[1] == pytest.approx(
        overall_time(6, TimeModel.STAIRCASE))


def test_the_staircase_inverse_is_two_valued_and_the_shorter_is_reported():
    """The price of the real calendar, stated rather than hidden.

    The staircase adds two days at every weekend, so the reference BED drops by
    two days' worth of proliferation there and then resumes climbing. A target
    falling in that drop is met by two fraction counts, one on each side of the
    jump, and both are exact. The solver reports the shorter, so that the
    equivalent dose is a function of its input. The ambiguity is bounded by the
    drop divided by the per-fraction gain: at most a fraction or so.
    """
    assert overall_time(5, TimeModel.STAIRCASE) == 5
    assert overall_time(6, TimeModel.STAIRCASE) == 8
    assert overall_time(20, TimeModel.STAIRCASE) == 26
    assert overall_time(40, TimeModel.STAIRCASE) == 54
    # Two days per weekend, and the rate 7/5 is its long-run slope.
    for sessions in (10, 20, 40, 80):
        assert abs(overall_time(sessions, TimeModel.STAIRCASE)
                   - sessions * 7 / 5) <= 2.4


def test_weekend_staircase_never_compresses_time():
    """Calendar time is non-decreasing in the number of fractions."""
    times = [overall_time(n, TimeModel.STAIRCASE) for n in range(0, 200)]
    assert all(b >= a for a, b in zip(times, times[1:]))
    # And never shorter than the fractions themselves, nor longer than 7/5 of them.
    for n, t in enumerate(times):
        assert t >= n
        assert t <= n * 7 / 5 + 2


def test_equivalent_dose_increases_with_delivered_dose(library):
    """More fractions of the same size must never mean less equivalent dose."""
    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")
    doses = [compute(organ, tumour,
                     Prescription(courses=(Course(2.0, n),), reference_dose=2.0),
                     LEGACY, library).eqd_tumour_total
             for n in range(1, 45)]
    assert all(b > a for a, b in zip(doses, doses[1:]))


def test_invalid_input_fails_loudly(library):
    """A calculator used clinically must refuse bad input, not absorb it."""
    with pytest.raises(ValueError):
        Prescription(courses=(Course(-1.0, 10),))
    with pytest.raises(ValueError):
        Prescription(courses=(Course(2.0, -5),))
    with pytest.raises(ValueError):
        Prescription(courses=(Course(2.0, 10, -3),))
    with pytest.raises(ValueError):
        Prescription(courses=(Course(2.0, 10),), reference_dose=-2.0)
    with pytest.raises(KeyError):
        library.organ("Not a tissue")


def test_the_two_sides_use_different_calendar_models(library):
    """A quirk of the 2014 model, reproduced and pinned here.

    The organ-at-risk branch converts fractions to calendar days through the
    seventeen-step weekend staircase; the tumour branch uses a plain 7/5 ratio.
    For 25 fractions that is 33 days against 35. Nothing in the published model
    justifies the asymmetry, and it is documented rather than silently aligned
    because aligning it would change every historical result.
    """
    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")
    for count in (10, 25, 35):
        result = compute(organ, tumour,
                         Prescription(courses=(Course(2.0, count),), reference_dose=2.0),
                         LEGACY, library)
        assert result.courses[0].overall_days_oar == pytest.approx(
            overall_time(count, TimeModel.STAIRCASE))
        assert result.courses[0].overall_days_tumour == pytest.approx(count * 7 / 5)
