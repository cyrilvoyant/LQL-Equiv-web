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
    options = Options.legacy_2014()
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
    """Values pinned directly from the 2014 application.

    Read under ``legacy_2014``, since that is what they are: what the 2014
    application printed. The software's own answer differs wherever the organ
    proliferates and the fraction size departs from the reference, which is the
    subject of ``docs/COMPARISON-2014.md``.
    """
    library = load_library()
    result = compute(
        library.organ(organ), library.tumour_site(tumour),
        Prescription(courses=(Course(dose, fractions),), reference_dose=2.0),
        Options.legacy_2014(),
    )
    assert result.eqd_oar_total == pytest.approx(expected_oar, abs=5e-3)


def test_the_manuscript_figure_replays_the_legacy_behaviour(golden_path):
    """Figure 1 compares against the 2014 application, so it must run that mode.

    The default options changed in August 2026 and this call did not, so the
    figure silently began comparing the current algorithm against MATLAB while
    its caption still quoted the legacy agreement: 92 % bit-identical printed
    over a panel showing 52 %. Nothing failed, because nothing checked.

    The three numbers the caption carries are asserted here against the dataset.
    """
    import pathlib

    source = (pathlib.Path(__file__).resolve().parent.parent
              / "paper" / "figures.py").read_text(encoding="utf-8")
    assert "replay(case, Options.legacy_2014())" in source, (
        "paper/figures.py must replay the 2014 behaviour for figure 1")

    fields = ("eqdtotal", "eqdttotal", "eqds1", "eqds2", "eqds3",
              "eqdt1", "eqdt2", "eqdt3")
    options = Options.legacy_2014()
    identical = total = 0
    largest = 0.0
    with golden_path.open(encoding="utf-8") as handle:
        for line in handle:
            case = json.loads(line)
            if "error" in case:
                continue
            mine = replay(case, options)
            for field in fields:
                a, b = _number(case["out"].get(field)), mine.get(field)
                if a is None or b is None:
                    continue
                total += 1
                identical += a == b
                largest = max(largest, abs(b - a))

    assert total == 34418
    assert identical / total == pytest.approx(0.920, abs=5e-4)
    assert largest == pytest.approx(0.04, abs=5e-4)
