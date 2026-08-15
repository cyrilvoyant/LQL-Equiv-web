"""Quantify the deviation between the 2014 MATLAB application and this port.

Reads the golden dataset captured from the original GUIDE application (see
``tools/matlab/sweep.m``), replays every case through :mod:`lqlequiv`, and
reports the deviation per output quantity. Used both by the test-suite and to
regenerate the numbers in ``docs/COMPARISON-2014.md``.

Usage::

    python tools/compare_with_2014.py tests/data/golden.jsonl [--markdown]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lqlequiv.model import Course, Options, Prescription, compute  # noqa: E402
from lqlequiv.tissues import load_library  # noqa: E402

#: Golden field -> (result attribute, human label)
SCALAR_FIELDS = {
    "eqdtotal": "total equivalent dose, organ at risk (Gy)",
    "eqdttotal": "total equivalent dose, tumour (Gy)",
    "text104": "complication probability (%)",
    "text105": "radiation-induced cancer risk",
}
PER_COURSE_FIELDS = {
    "eqds": "equivalent dose per course, organ at risk (Gy)",
    "eqdt": "equivalent dose per course, tumour (Gy)",
    "bede": "biologically effective dose per course, organ at risk (Gy)",
    "bedet": "biologically effective dose per course, tumour (Gy)",
}


@dataclass
class Deviation:
    """Accumulated deviation statistics for one output quantity."""

    label: str
    n: int = 0
    n_compared: int = 0
    max_abs: float = 0.0
    sum_abs: float = 0.0
    worst_case: dict | None = None
    n_only_matlab: int = 0

    def add(self, reference: float, ported: float, case: dict) -> None:
        self.n += 1
        if reference is None or ported is None:
            self.n_only_matlab += 1
            return
        if math.isnan(reference) or math.isnan(ported):
            return
        self.n_compared += 1
        error = abs(reference - ported)
        self.sum_abs += error
        if error > self.max_abs:
            self.max_abs = error
            self.worst_case = {"case": case, "matlab": reference, "python": ported}

    @property
    def mean_abs(self) -> float:
        return self.sum_abs / self.n_compared if self.n_compared else 0.0


def _number(text: str) -> float | None:
    """Parse one of the strings the MATLAB interface writes into its fields."""
    text = (text or "").strip()
    if text in {"", "?", "NC", "Hum", "Bizarre"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def replay(case: dict, options: Options) -> dict[str, float | None]:
    """Run one golden case through the Python implementation."""
    inputs = case["in"]
    library = load_library()
    courses = tuple(
        Course(inputs[f"d{i}"], inputs[f"nf{i}"], inputs[f"ja{i}"]) for i in (2, 3, 4)
    )
    prescription = Prescription(
        courses=courses,
        reference_dose=inputs["d1"],
        bifractionated=bool(inputs["bifrac"]),
    )
    result = compute(
        library.organ(int(inputs["oar"])),
        library.tumour_site(int(inputs["tum"])),
        prescription,
        options,
    )
    out: dict[str, float | None] = {
        "eqdtotal": result.eqd_oar_total if result.oar_total_valid else None,
        "eqdttotal": result.eqd_tumour_total if result.tumour_total_valid else None,
        "text104": result.ntcp_percent,
        "text105": result.cancer_risk,
    }
    for position, course in enumerate(result.courses, start=1):
        out[f"eqds{position}"] = course.eqd_oar
        out[f"eqdt{position}"] = course.eqd_tumour
        out[f"bede{position}"] = course.bed_oar
        out[f"bedet{position}"] = course.bed_tumour
    return out


def run(path: Path, options: Options | None = None) -> dict[str, Deviation]:
    options = options or Options()
    stats: dict[str, Deviation] = {}
    for key, label in SCALAR_FIELDS.items():
        stats[key] = Deviation(label)
    for key, label in PER_COURSE_FIELDS.items():
        stats[key] = Deviation(label)

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            case = json.loads(line)
            if "error" in case:
                continue
            ported = replay(case, options)
            golden = case["out"]
            for key in SCALAR_FIELDS:
                stats[key].add(_number(golden.get(key)), ported.get(key), case["in"])
            for prefix in PER_COURSE_FIELDS:
                for position in (1, 2, 3):
                    stats[prefix].add(
                        _number(golden.get(f"{prefix}{position}")),
                        ported.get(f"{prefix}{position}"),
                        case["in"],
                    )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("golden", type=Path)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--exact", action="store_true",
                        help="disable the 2014 grid quantisation")
    args = parser.parse_args()

    options = Options(legacy_quantisation=not args.exact)
    stats = run(args.golden, options)

    if args.markdown:
        print("| Quantity | Compared | Max deviation | Mean deviation |")
        print("| --- | ---: | ---: | ---: |")
        for dev in stats.values():
            print(f"| {dev.label} | {dev.n_compared} | {dev.max_abs:.3e} | {dev.mean_abs:.3e} |")
    else:
        for dev in stats.values():
            print(f"{dev.label}")
            print(f"  compared {dev.n_compared}/{dev.n}  "
                  f"max {dev.max_abs:.6g}  mean {dev.mean_abs:.6g}")
            if dev.worst_case and dev.max_abs > 1e-6:
                print(f"  worst: {dev.worst_case}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
