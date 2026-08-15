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
from lqlequiv.model import _incomplete_repair, _lql_dose_term, _tumour_dprol
from lqlequiv.schedule import TimeModel, overall_time

EXACT = Options(legacy_quantisation=False, time_model=TimeModel.STAIRCASE)


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
    # the proliferation dose by 2e-4 in relative terms. Pinned, not corrected:
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
                     EXACT, library)
    assert result.courses[0].bed_tumour == pytest.approx(expected, rel=1e-9)


def test_no_proliferation_loss_before_the_kick_off_time(library):
    """Below ``Tk`` the term is switched off, and switches on continuously."""
    tumour = library.tumour_site("Standard tumour")
    organ = library.organ("Spinal cord")
    dprol = _tumour_dprol(tumour)

    short = compute(organ, tumour,
                    Prescription(courses=(Course(2.0, 10),), reference_dose=2.0),
                    EXACT, library)
    assert 10 * 7 / 5 < tumour.Tk
    assert short.courses[0].bed_tumour == pytest.approx(
        10 * 2.0 * (1 + 2.0 / tumour.alpha_beta), rel=1e-9)

    # Just past the kick-off the loss equals dprol times the excess time.
    for count in (16, 17):
        time = count * 7 / 5
        result = compute(organ, tumour,
                         Prescription(courses=(Course(2.0, count),), reference_dose=2.0),
                         EXACT, library)
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
                                          reference_dose=dose), EXACT, library)
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
                     EXACT, library).eqd_tumour_total
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
                         EXACT, library)
        assert result.courses[0].overall_days_oar == pytest.approx(
            overall_time(count, TimeModel.STAIRCASE))
        assert result.courses[0].overall_days_tumour == pytest.approx(count * 7 / 5)
