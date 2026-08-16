# LQL-Equiv

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21948624.svg)](https://doi.org/10.5281/zenodo.21948624)
[![tests](https://github.com/cyrilvoyant/LQL-Equiv-web/actions/workflows/ci.yml/badge.svg)](https://github.com/cyrilvoyant/LQL-Equiv-web/actions/workflows/ci.yml)
[![licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Biologically equivalent doses in radiotherapy, under the linear-quadratic-linear model.**

### ▶ [Open the calculator](https://cyrilvoyant.github.io/LQL-Equiv-web/) — free, no installation, runs entirely in your browser

A Python library and web application computing biologically effective dose (BED),
equivalent dose in a reference fractionation (EQD2 and others), normal-tissue
complication probability (NTCP), tumour control probability (TCP) and
radiation-induced cancer risk, with corrections for incomplete inter-fraction
repair, accelerated proliferation and treatment protraction.

This is version 3.0, a complete reimplementation of the 2014 MATLAB application
[`cyrilvoyant/LQ-Equiv`](https://github.com/cyrilvoyant/LQ-Equiv), compared
case by case against it over 4438 treatment schedules. It solves the equations
that release was published with, which for the organ at risk is not what its
source computed — see
[`docs/COMPARISON-2014.md`](docs/COMPARISON-2014.md).

> [!WARNING]
> **For research and education only. Not intended for clinical use.**
> This software is not a medical device. Stated as a list rather than as a
> generality, its outputs must not be used to choose or modify a prescription,
> to compute the compensation for a real interruption, to sum dose in a
> reirradiation decision, to accept or reject a treatment plan, to support a
> consent discussion, or to predict complication or control probability for an
> individual patient.
>
> The complication and control probabilities deserve a separate warning. They are
> point estimates on a single equivalent dose, computed from the 2014 parameter
> library whose Lyman values fall in the range of the 1991 Emami/Burman fits and
> predate QUANTEC. They carry no volume information, and they have never been
> validated against clinical outcome. Read them as illustrations of a model's
> shape, never as a risk for a patient.

---

## What it does

Given an organ at risk, a tumour site and a sequence of successive treatment
courses separated by gaps, it computes:

| Quantity | Model |
| --- | --- |
| Biologically effective dose | Linear-quadratic with the linear tail of Astrahan above the transition dose |
| Proliferation, target | Dale: nothing lost before the kick-off time `Tk` |
| Proliferation, organ at risk | Van Dyk: a recovered dose from the first day, no kick-off time |
| Overall time | Five days a week, weekends and missed sessions included, one calendar for both tissues |
| Two fractions a day | Thames' incomplete-repair correction, six-hour interval |
| Equivalent dose | Dose in the chosen reference fractionation giving the same BED |
| Complication probability | Lyman probit, organs at risk only |
| Tumour control probability | Logistic or Poisson sigmoid in γ50 — **new in 3.0** |
| Radiation-induced cancer risk | Linear-exponential |

The shipped radiobiological library holds **34 organs at risk** and **20 tumour
sites** — the 19 transcribed from the 2014 release, plus a standard tumour with
proliferation switched off, which gives a reference case where equivalent dose
depends on fractionation alone. Every value's provenance is recorded in
[`docs/PARAMETERS.md`](docs/PARAMETERS.md).

## Use it

**In the browser, nothing to install** — the application runs entirely on your
machine, inside the page; no data is sent anywhere.

**Locally:**

```bash
pip install -e ".[app]"
streamlit run app/streamlit_app.py
```

**As a library:**

```python
from lqlequiv import Course, Prescription, compute, load_library

library = load_library()
plan = Prescription(courses=(Course(dose_per_fraction=2.0, n_fractions=39),),
                    reference_dose=2.0)
result = compute(library.organ("Rectum"), library.tumour_site("Prostate"), plan)

print(result.eqd_oar_total)   # 78.0 Gy EQD2 to the rectum
print(result.ntcp_percent)    # complication probability, proctitis
print(result.tcp_percent)     # tumour control probability
```

The core package depends only on the Python standard library.

## Validation

The 2014 GUIDE application was driven headless over **4 438 treatment
schedules** — every organ-at-risk/tumour pair, a wide fractionation grid, gaps,
two-fractions-a-day schedules and randomised multi-course plans — and its
outputs captured as a golden dataset ([`tests/data/golden.jsonl`](tests/data/golden.jsonl),
produced by [`tools/matlab/sweep.m`](tools/matlab/sweep.m)).

| | |
| --- | --- |
| Values compared | 69 131 |
| **Agreeing at MATLAB's output precision** | **69 125 (99.991 %)** |
| Cases differing | 2 of 4 438 (0.05 %) |

The two differing cases are exact ties, where the true root falls precisely
halfway between two points of the 2014 search grid and the original result is
settled by floating-point noise at the fifteenth decimal. The full analysis is
in [`docs/COMPARISON-2014.md`](docs/COMPARISON-2014.md).

**What this validates, and what it does not.** Agreeing with the 2014 application
shows that the port is faithful; it cannot show that either is right. The
software therefore also asserts properties of the equations themselves, with no
reference implementation in the loop: continuity at the transition dose, the
identity `EQD = n·d` at the reference fraction size, additivity across split
courses, and the round trip — delivering the reported dose at the reference
fraction size must reproduce the BED it replaced. That last one is what
identified the organ-at-risk difference below.

`Options.legacy_2014()` reproduces the 2014 behaviour, including its search grid
of hundredths of a fraction stopping at 100 and its calendar contradiction past
86 fractions. It exists for recomputing a result published before 2026 and for
the non-regression suite; nothing else uses it.

Separately, the closed-form search that replaces the original exhaustive scan is
proved equivalent to it: [`tools/verify_grid_equivalence.py`](tools/verify_grid_equivalence.py)
replays all 20 001 grid points for every case and reports **0 disagreements**
over 10 554 searches.

```bash
pytest                 # unit tests and the golden non-regression suite
pytest -m slow         # the grid-equivalence replay alone (needs numpy)
```

## What changed since 2014

Beyond the port itself, the reimplementation surfaced several defects in the
original release. All are documented, and all remain reachable through
`Options.legacy_2014()` rather than being silently corrected:

- **The organ-at-risk equivalent dose did not satisfy its own definition.** The
  source reported `n_r · d_r − (T − T_r) · dprol`, where the 2014 paper's
  equation (12) defines it as `n_r · d_r`. The subtracted term charges a second
  time a span the solved `n_r` had already balanced: for a rectum receiving
  20 × 3 Gy, the reported 82.69 Gy delivered at 2 Gy per fraction carries a BED
  of 107.74 Gy against the schedule's own 97.75 Gy. Version 3.0 reports 75.25 Gy
  and the round trip closes. **This is the only one that changes an answer a
  department would read.**
- **Tumour control probability was never computed.** The library held dose-response
  parameters for eleven tumour sites that no code path used. They are γ50 and
  TCD50 values, not Lyman parameters — which is probably why they went unused.
- **Nine parameters were displayed differently from the values used** in the
  computation, across seven tissues.
- **The calendar model contradicts itself past 86 fractions**, where two
  copies of the same weekend staircase diverge by up to a day.
- **Complication probability was reported as 100 % for tissues with no Lyman
  parameters**, through a division by zero. It is now reported as unavailable.

What is *not* changed: the two tissues keep the two proliferation models the 2014
paper gives them, Dale with a kick-off time for the target volume and Van Dyk
without one for the organ at risk.

See [`docs/COMPARISON-2014.md`](docs/COMPARISON-2014.md) for the arithmetic, the
round-trip criterion and the size of the difference across 7850 schedules.

## Frequently asked questions

**What is the linear-quadratic-linear model?**
The linear-quadratic model overestimates cell kill at high dose per fraction. The
linear-quadratic-linear model of Astrahan replaces the quadratic term by a
straight line above a transition dose, which makes it usable for the large
fractions of stereotactic radiotherapy. In this library the transition dose is
twice the α/β ratio for every tissue.

**What is EQD2, and how does it differ from BED?**
BED is a model quantity with no direct clinical meaning; EQD2 is the dose which,
delivered in 2 Gy fractions, would produce the same biological effect as the
schedule under consideration. EQD2 is what lets two schedules with different
fraction sizes be compared. Any reference fraction size can be used here, not
only 2 Gy.

**Which way does proliferation move the equivalent dose?**
Both ways, depending on whether the schedule runs longer or shorter than the
reference schedule it is being matched against. Proliferation penalises *both*
sides of the comparison, and the longer side loses more. Against the standard
tumour, which proliferates at 0.66 Gy/day past a kick-off time of 21 days:

*A schedule prolonged by a treatment gap — 25 × 2 Gy, reference 2 Gy:*

| Gap | Standard tumour | Proliferation switched off |
| ---: | ---: | ---: |
| 0 days | 50.00 Gy | 50.00 Gy |
| 10 days | **37.48 Gy** | 50.00 Gy |
| 30 days | 19.20 Gy | 50.00 Gy |

Here proliferation lowers the equivalent dose, and a ten-day interruption costs
12.5 Gy EQD2 — more than six 2 Gy fractions. With proliferation switched off a gap
costs nothing at all. Note the zero-gap row: both tumours give exactly 50 Gy even
though their BEDs differ (50.76 against 60.00), because the schedule *is* the
reference schedule and the proliferation loss cancels on both sides.

*A schedule shortened by hypofractionation — 20 × 3 Gy, reference 2 Gy:*

| | BED | EQD2 | equivalent reference schedule |
| --- | ---: | ---: | --- |
| Standard tumour | 73.38 | **80.66** | 40.33 fractions, 56.5 days |
| Proliferation switched off | 78.00 | 65.00 | 32.50 fractions, 45.5 days |

Here it goes the other way: the 20-fraction schedule runs 28 days and loses
0.66 × 7 ≈ 4.6 Gy, while the reference schedule matched to it runs 56.5 days and
loses 0.66 × 35.5 ≈ 23 Gy — five times as much — so more reference dose is needed
and the equivalent dose rises. This is the familiar result that short accelerated
schedules are favoured in fast-proliferating tumours.

Isolating this effect is what the added non-proliferating tumour is for.

**Can this be used to treat a patient?**
No. It is for research and education only, it is not a medical device, and it
must not be used to plan, verify or modify a patient's treatment.

**Is any data sent to a server?**
No computation happens on a server. The page embeds the model and fetches the
version-pinned stlite and Pyodide runtime from a public CDN on first load, then
runs everything locally. The network sees that the page was visited and never
what was entered into it.

**How is it related to LQ-Equiv?**
[`cyrilvoyant/LQ-Equiv`](https://github.com/cyrilvoyant/LQ-Equiv) is the 2014
MATLAB application, distributed as a Windows executable requiring the MATLAB
Component Runtime. This repository is its successor: same models, same
radiobiological library, reimplemented in Python.

**Does it return the same numbers as LQ-Equiv?**
For the target volume, yes. For the organ at risk, no, and deliberately. The 2014
source reported `n_r · d_r − (T − T_r) · dprol`, where its own paper defines the
equivalent dose as `n_r · d_r` (equation 12). The subtracted term charges a second
time a span the solved `n_r` had already balanced, and the result does not satisfy
the equality it comes from: for a rectum receiving 20 × 3 Gy the 2014 value of
82.69 Gy, delivered at 2 Gy per fraction, carries a BED of 107.74 Gy against the
schedule's own 97.75 Gy. Version 3.0 reports 75.25 Gy and the round trip closes.
[`docs/COMPARISON-2014.md`](docs/COMPARISON-2014.md) gives the arithmetic and the
size of the difference across 7850 schedules; `Options.legacy_2014()` recovers the
2014 behaviour for anyone recomputing a published result.

**Which model is used for each endpoint?**
BED and equivalent dose use the linear-quadratic-linear model of Astrahan and,
for two fractions a day, the incomplete-repair correction of Thames.
Proliferation follows Dale for the target volume, with a kick-off time, and Van
Dyk for the organ at risk, without one — the two are different models, as the
2014 paper sets out in its sections 3.1 and 3.2. Complication probability uses
the Lyman probit. Tumour control probability uses a logistic or Poisson sigmoid
in γ50.

## Citation

If you use this software, cite the methodology paper and the software (see
[`CITATION.cff`](CITATION.cff)):

- Voyant C, Julian D, Roustit R, Biffi K, Lantieri C. Biological effects and
  equivalent doses in radiotherapy: a software solution. *Reports of Practical
  Oncology and Radiotherapy* 2014;19(1):47–55.
  [doi:10.1016/j.rpor.2013.08.004](https://doi.org/10.1016/j.rpor.2013.08.004)
- Voyant C, Julian D. A short synthesis concerning biological effects and
  equivalent doses in radiotherapy. *Journal of Radiology and Oncology*
  2017;1:039–045.
  [doi:10.29328/journal.jro.1001005](https://doi.org/10.29328/journal.jro.1001005)
- Improving clinical decision-making in radiotherapy: a comparative analysis of
  linear-quadratic (LQ) and linear-quadratic-linear (LQL) dose models.
  *Clinical Oncology* 2025;45.
  [doi:10.1016/j.clon.2025.103893](https://doi.org/10.1016/j.clon.2025.103893)
- This software: Voyant C, Julian D. LQL-Equiv-web: a Python and web
  implementation of biologically equivalent dose calculation in radiotherapy
  (Version 3.0.0) [Computer software]. Zenodo, 2026.
  [doi:10.5281/zenodo.21948624](https://doi.org/10.5281/zenodo.21948624) —
  use the concept DOI
  [10.5281/zenodo.21948623](https://doi.org/10.5281/zenodo.21948623) to cite all
  versions.
- The original MATLAB application, archived on Zenodo:
  [doi:10.5281/zenodo.16739883](https://doi.org/10.5281/zenodo.16739883)

## Authors

**Cyril Voyant** — [ORCID 0000-0003-0242-7377](https://orcid.org/0000-0003-0242-7377)
Mines Paris, PSL University — Centre for Observation, Impacts, Energy (O.I.E.),
Sophia-Antipolis 06904, France · `cyril.voyant@minesparis.psl.eu` · *corresponding author*

**Daniel Julian**
Centre de Cancérologie du Grand Montpellier — Radiotherapy Unit,
Montpellier 34000, France · `Julian@ccgm.fr`

## Licence

Released under the [MIT licence](LICENSE).
