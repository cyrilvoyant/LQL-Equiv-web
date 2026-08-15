"""Prove the closed-form search agrees with the 2014 exhaustive grid search.

The 2014 application finds an equivalent fraction count by evaluating its
objective at every point of a grid of hundredths of a fraction and taking the
minimum. This package instead solves the objective in closed form and scores
only the handful of grid points around each root, which is far faster but is
only legitimate if it lands on the *same* grid point every time.

That is not obvious: repopulation switches on at the kick-off time, which makes
the tumour objective piecewise linear, so it can approach the target twice and
its best grid point can sit next to the kink rather than next to a root.

This script settles the question empirically. For every case of the golden
dataset it replays the full grid with numpy and compares the exhaustive
minimiser against the one the package returned. Any disagreement is reported
with enough context to reproduce it.

Usage::

    python tools/verify_grid_equivalence.py tests/data/golden.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lqlequiv.model import (
    Course,
    Options,
    Prescription,
    _lql_dose_term,
    _tumour_dprol,
    compute,
)
from lqlequiv.tissues import load_library

GRID = 0.01


def _oar_grid(bed: float, reference: float, tissue, gamma: float) -> float:
    counts = np.arange(0, 10001) * GRID
    values = counts * _lql_dose_term(reference, tissue, gamma, 0.0) - (
        counts * 7.0 / 5.0
    ) * tissue.dprol
    return float(counts[int(np.argmin(np.abs(bed - values)))])


def _tumour_grid(
    bed: float, reference: float, days_before: float, tissue, gamma: float, dprol: float
) -> float:
    counts = np.arange(-10000, 10001) * GRID
    elapsed = counts * 7.0 / 5.0
    already = (tissue.Tk - days_before) * (1.0 if tissue.Tk - days_before > 0 else 0.0)
    switch = (days_before + elapsed - tissue.Tk) > 0
    values = counts * _lql_dose_term(reference, tissue, gamma, 0.0) - switch * dprol * (
        elapsed - already
    )
    return float(counts[int(np.argmin(np.abs(bed - values)))])


def verify(path: Path) -> int:
    library = load_library()
    gamma = library.gamma_over_alpha
    options = Options()
    checked = disagreements = 0

    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            case = json.loads(line)
            if "error" in case:
                continue
            inputs = case["in"]
            oar = library.organ(int(inputs["oar"]))
            tum = library.tumour_site(int(inputs["tum"]))
            prescription = Prescription(
                courses=tuple(
                    Course(inputs[f"d{i}"], inputs[f"nf{i}"], inputs[f"ja{i}"])
                    for i in (2, 3, 4)
                ),
                reference_dose=inputs["d1"],
                bifractionated=bool(inputs["bifrac"]),
            )
            result = compute(oar, tum, prescription, options, library)
            dprol = _tumour_dprol(tum)
            equivalent_days = 0.0

            for position, (course, row) in enumerate(
                zip(prescription.courses, result.courses), 1
            ):
                empty = course.is_empty or prescription.reference_dose == 0.0
                if not empty:
                    checked += 2
                    exhaustive = _oar_grid(row.bed_oar, prescription.reference_dose, oar, gamma)
                    if abs(exhaustive - row.equivalent_fractions_oar) > 1e-9:
                        disagreements += 1
                        print(f"line {line_number} course {position} ORGAN "
                              f"grid={exhaustive} closed-form={row.equivalent_fractions_oar} "
                              f"{inputs}")
                    exhaustive = _tumour_grid(
                        row.bed_tumour, prescription.reference_dose, equivalent_days,
                        tum, gamma, dprol,
                    )
                    if abs(exhaustive - row.equivalent_fractions_tumour) > 1e-9:
                        disagreements += 1
                        print(f"line {line_number} course {position} TUMOUR "
                              f"grid={exhaustive} closed-form={row.equivalent_fractions_tumour} "
                              f"{inputs}")
                equivalent_days += max(row.equivalent_fractions_tumour, 0.0) * 7.0 / 5.0

    print(f"\n{checked} searches replayed against the full grid")
    print(f"{disagreements} disagreement(s)")
    return 1 if disagreements else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("golden", type=Path)
    return verify(parser.parse_args().golden)


if __name__ == "__main__":
    raise SystemExit(main())
