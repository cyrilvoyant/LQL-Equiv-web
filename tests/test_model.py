"""Unit tests for the linear-quadratic-linear model."""

from __future__ import annotations

import pytest

from lqlequiv import Course, Options, Prescription, TCPModel, compute, load_library
from lqlequiv.model import (
    normal_tissue_complication_probability,
    radiation_induced_cancer_risk,
    tumour_control_probability,
)
from lqlequiv.schedule import TimeModel, course_days, overall_time


@pytest.fixture(scope="module")
def library():
    return load_library()


def test_library_is_complete(library):
    """The 2014 library, plus whatever 3.0 added on top of it, clearly separated."""
    original_oar = [t for t in library.oar if t.is_from_2014_release]
    original_tumour = [t for t in library.tumour if t.is_from_2014_release]
    assert len(original_oar) == 34
    assert len(original_tumour) == 19
    assert len(library.oar) == 34
    assert len(library.tumour) == 20
    assert library.gamma_over_alpha == 5.0


def test_added_entries_declare_their_origin(library):
    for tissue in library.oar + library.tumour:
        if not tissue.is_from_2014_release:
            assert tissue.source, f"{tissue.name} must say where it comes from"


def test_standard_tumour_without_repopulation_isolates_fractionation(library):
    """The added reference tumour removes the overall-time term entirely.

    Against the standard tumour, which repopulates at 0.66 Gy/day, the two
    differ only by the time effect; in the reference fractionation, where there
    is no time effect to speak of, they agree.
    """
    organ = library.organ("Rectum")
    standard = library.tumour_site("Standard tumour")
    neutral = library.tumour_site("Standard tumour, no repopulation")

    reference = Prescription(courses=(Course(2.0, 30),), reference_dose=2.0)
    assert compute(organ, standard, reference).eqd_tumour_total == pytest.approx(
        compute(organ, neutral, reference).eqd_tumour_total, abs=0.02
    )

    hypofractionated = Prescription(courses=(Course(3.0, 20),), reference_dose=2.0)
    with_time = compute(organ, standard, hypofractionated).eqd_tumour_total
    without_time = compute(organ, neutral, hypofractionated).eqd_tumour_total
    assert with_time > without_time
    # A gap costs the repopulating tumour dose and the neutral one nothing.
    delayed = Prescription(courses=(Course(3.0, 20, 14),), reference_dose=2.0)
    assert compute(organ, neutral, delayed).eqd_tumour_total == pytest.approx(without_time)
    assert compute(organ, standard, delayed).eqd_tumour_total < with_time


def test_transition_dose_is_twice_alpha_beta(library):
    """The shipped library sets the LQL transition dose at 2 alpha/beta."""
    for tissue in library.oar + library.tumour:
        assert tissue.dt == pytest.approx(2 * tissue.alpha_beta)


def test_reference_schedule_is_its_own_equivalent(library):
    """A course delivered in the reference fractionation is its own equivalent."""
    plan = Prescription(courses=(Course(2.0, 30),), reference_dose=2.0)
    result = compute(library.organ("Rectum"), library.tumour_site("Prostate"), plan)
    assert result.eqd_oar_total == pytest.approx(60.0, abs=0.02)
    assert result.eqd_tumour_total == pytest.approx(60.0, abs=0.02)


def test_hypofractionation_raises_late_tissue_dose(library):
    """Fewer, larger fractions cost more in a low alpha/beta tissue."""
    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")
    conventional = compute(organ, tumour, Prescription(courses=(Course(2.0, 30),)))
    hypofractionated = compute(organ, tumour, Prescription(courses=(Course(3.0, 20),)))
    assert hypofractionated.eqd_oar_total > conventional.eqd_oar_total


def test_ntcp_is_a_normal_tissue_quantity(library):
    """Complication probability is defined for organs at risk only."""
    organ = library.organ("Rectum")
    tumour = library.tumour_site("Prostate")
    assert organ.has_ntcp
    assert tumour.has_tcp
    assert normal_tissue_complication_probability(organ.d50, organ) == pytest.approx(50.0)


def test_ntcp_reported_absent_rather_than_fabricated(library):
    """Tissues with no Lyman parameters report nothing, not a certainty.

    The 2014 application divided by zero here and displayed 100 percent.
    """
    organ = library.organ("Oral mucosa")
    assert not organ.has_ntcp
    assert normal_tissue_complication_probability(50.0, organ) is None


def test_tumour_slopes_are_not_lyman_slopes(library):
    """The tumour dose-response slopes are gamma50, far outside any Lyman range.

    This is why the 2014 application could not feed them to its probit and left
    them unused.
    """
    lyman = [t.m for t in library.oar if t.has_ntcp]
    gamma50 = [t.gamma50 for t in library.tumour if t.has_tcp]
    assert max(lyman) < 0.3
    assert max(gamma50) > 3.0


def test_tcp_rises_with_dose_and_reaches_half_at_tcd50(library):
    tumour = library.tumour_site("Prostate")
    at_half = tumour_control_probability(tumour.tcd50, tumour)
    assert at_half == pytest.approx(50.0)
    assert tumour_control_probability(20.0, tumour) < at_half
    assert tumour_control_probability(90.0, tumour) > at_half


@pytest.mark.parametrize("model", [TCPModel.LOGISTIC, TCPModel.POISSON])
def test_tcp_is_monotonic(library, model):
    tumour = library.tumour_site("Tonsil")
    values = [tumour_control_probability(dose, tumour, model) for dose in range(0, 120, 5)]
    assert all(b >= a for a, b in zip(values, values[1:]))


def test_cancer_risk_absent_when_no_coefficient(library):
    assert radiation_induced_cancer_risk(60.0, library.organ("Brain")) is None
    assert radiation_induced_cancer_risk(60.0, library.organ("Lung")) is not None


def test_weekend_staircase_matches_the_hand_written_steps():
    """The closed form reproduces the seventeen steps written out in 2014."""
    assert overall_time(5) == 5
    assert overall_time(6) == 8
    assert overall_time(10) == 12
    assert overall_time(25) == 33
    assert overall_time(85) == 117


def test_calendar_models_agree_below_the_cut_off():
    for count in range(0, 86):
        assert overall_time(count, TimeModel.LEGACY) == overall_time(count, TimeModel.STAIRCASE)


def test_calendar_models_diverge_at_the_2014_cut_off():
    """Past 86 fractions the 2014 fallback steps off the staircase."""
    assert overall_time(86, TimeModel.LEGACY) == pytest.approx(120.4)
    assert overall_time(86, TimeModel.STAIRCASE) == pytest.approx(120.0)


def test_bifractionation_halves_the_treatment_days():
    assert course_days(40, 0, bifractionated=False) == pytest.approx(overall_time(40))
    assert course_days(40, 0, bifractionated=True) == pytest.approx(overall_time(20))
    # An odd fraction count rounds up to a whole treatment day.
    assert course_days(41, 0, bifractionated=True) == pytest.approx(overall_time(21))


def test_exact_and_legacy_quantisation_stay_within_one_grid_step(library):
    plan = Prescription(courses=(Course(2.7, 18),), reference_dose=2.0)
    organ, tumour = library.organ("Rectum"), library.tumour_site("Prostate")
    legacy = compute(organ, tumour, plan, Options(legacy_quantisation=True))
    exact = compute(organ, tumour, plan, Options(legacy_quantisation=False))
    assert abs(legacy.eqd_oar_total - exact.eqd_oar_total) <= 0.01 * plan.reference_dose


def test_empty_prescription_yields_nothing(library):
    result = compute(library.organ("Rectum"), library.tumour_site("Prostate"),
                     Prescription(courses=(Course(0, 0),)))
    assert result.eqd_oar_total == 0.0
    assert result.eqd_tumour_total == 0.0


def test_invalid_prescriptions_are_rejected():
    with pytest.raises(ValueError):
        Prescription(courses=(Course(-2.0, 10),))
    with pytest.raises(ValueError):
        Prescription(courses=(Course(2.0, 10),) * 4)


def test_display_mismatches_of_2014_are_recorded(library):
    """The 2014 interface showed nine values it did not compute with."""
    assert len(library.mismatches) == 9
    names = {m.name for m in library.mismatches}
    assert "Heart" in names
    assert "Prostate" in names
