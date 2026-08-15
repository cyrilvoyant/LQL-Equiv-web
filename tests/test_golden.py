"""Non-regression against the original MATLAB application.

The golden dataset was captured by driving the 2014 GUIDE application headless
over 4438 schedules; see ``tools/matlab/sweep.m``. MATLAB writes its interface
fields with six significant digits, which is therefore the resolution at which
the two implementations can be compared at all.
"""

from __future__ import annotations

import json

import pytest

from compare_with_2014 import _number, replay
from lqlequiv import Course, Prescription, compute, load_library
from lqlequiv.model import Options

#: Fields captured from the 2014 interface.
FIELDS = (
    "eqdtotal", "eqdttotal", "eqds1", "eqds2", "eqds3", "eqdt1", "eqdt2", "eqdt3",
    "bede1", "bede2", "bede3", "bedet1", "bedet2", "bedet3", "text104", "text105",
)

#: Cases where the exact root falls halfway between two grid points, leaving the
#: 2014 answer to be decided by floating-point noise. See docs/COMPARISON-2014.md.
TOLERATED_TIE_CASES = 2


def _six_significant_digits(value):
    return value if value is None or value == 0 else float("%.6g" % value)


def test_matches_the_2014_application(golden_path):
    options = Options()
    compared = agreed = 0
    disagreeing_cases = set()

    with golden_path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            case = json.loads(line)
            if "error" in case:
                continue
            ported = replay(case, options)
            for field in FIELDS:
                reference = _number(case["out"].get(field))
                mine = ported.get(field)
                if reference is None or mine is None:
                    continue
                compared += 1
                if _six_significant_digits(mine) == reference or abs(reference - mine) < 5e-10:
                    agreed += 1
                else:
                    disagreeing_cases.add(number)

    assert compared > 60000, "golden dataset looks truncated"
    assert len(disagreeing_cases) <= TOLERATED_TIE_CASES, (
        f"{len(disagreeing_cases)} cases disagree with the 2014 application, "
        f"expected at most {TOLERATED_TIE_CASES} floating-point ties"
    )
    assert agreed / compared > 0.9999


@pytest.mark.parametrize(
    ("organ", "tumour", "dose", "fractions", "expected_oar"),
    [
        ("Temporomandibular joint", "Tonsil", 2.0, 25, 50.0),
        ("Temporomandibular joint", "Tonsil", 3.0, 15, 62.574),
        ("Spinal cord", "Tonsil", 2.0, 25, 50.0),
        ("Lung", "Oral mucosa", 2.0, 30, 60.0),
    ],
)
def test_reference_cases(organ, tumour, dose, fractions, expected_oar):
    """Values pinned directly from the 2014 application."""
    library = load_library()
    result = compute(
        library.organ(organ), library.tumour_site(tumour),
        Prescription(courses=(Course(dose, fractions),), reference_dose=2.0),
    )
    assert result.eqd_oar_total == pytest.approx(expected_oar, abs=5e-3)
