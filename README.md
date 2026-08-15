# LQL-Equiv

**Biologically equivalent doses in radiotherapy, under the linear-quadratic-linear model.**

A Python library and web application computing biologically effective dose (BED),
equivalent dose in a reference fractionation (EQD2 and others), normal-tissue
complication probability (NTCP), tumour control probability (TCP) and
radiation-induced cancer risk, with corrections for incomplete inter-fraction
repair, accelerated repopulation and treatment protraction.

This is version 3.0, a complete reimplementation of the 2014 MATLAB application
[`cyrilvoyant/LQ-Equiv`](https://github.com/cyrilvoyant/LQ-Equiv), validated case
by case against it.

> [!WARNING]
> **For research and education only. Not intended for clinical use.**
> This software is not a medical device. It must not be used to plan, verify or
> modify the treatment of a patient.

---

## What it does

Given an organ at risk, a tumour site, and up to three successive treatment
courses separated by gaps, it computes:

| Quantity | Model |
| --- | --- |
| Biologically effective dose | Linear-quadratic with the linear tail of Astrahan above the transition dose |
| Repopulation | Dale, with a kick-off time and a daily dose consumption |
| Two fractions a day | Thames' incomplete-repair correction, six-hour interval |
| Equivalent dose | Dose in the chosen reference fractionation giving the same BED |
| Complication probability | Lyman probit, organs at risk only |
| Tumour control probability | Logistic or Poisson sigmoid in γ50 — **new in 3.0** |
| Radiation-induced cancer risk | Linear-exponential |

The shipped radiobiological library holds **34 organs at risk** and **19 tumour
sites**, transcribed from the 2014 release. Every value's provenance is recorded
in [`docs/PARAMETERS.md`](docs/PARAMETERS.md).

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

Separately, the closed-form search that replaces the original exhaustive scan is
proved equivalent to it: [`tools/verify_grid_equivalence.py`](tools/verify_grid_equivalence.py)
replays all 20 001 grid points for every case and reports **0 disagreements**
over 10 554 searches.

```bash
pytest                 # unit tests and the golden non-regression suite
pytest -m slow         # plus the full grid-equivalence replay (needs numpy)
```

## What changed since 2014

Beyond the port itself, the reimplementation surfaced several defects in the
original release, all documented and reproduced-by-default rather than silently
corrected:

- **Tumour control probability was never computed.** The library held dose-response
  parameters for eleven tumour sites that no code path used. They are γ50 and
  TCD50 values, not Lyman parameters — which is probably why they went unused.
- **Nine parameters were displayed differently from the values used** in the
  computation, across seven tissues.
- **The calendar model contradicts itself past 86 fractions**, where two
  copies of the same weekend staircase diverge by up to a day.
- **Complication probability was reported as 100 % for tissues with no Lyman
  parameters**, through a division by zero. It is now reported as unavailable.

See [`docs/COMPARISON-2014.md`](docs/COMPARISON-2014.md) for the quantified
comparison and the improvement axes.

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
- The original MATLAB application, archived on Zenodo:
  [doi:10.5281/zenodo.16739883](https://doi.org/10.5281/zenodo.16739883)

## Contributors

- **Cyril Voyant** — [ORCID 0000-0003-0242-7377](https://orcid.org/0000-0003-0242-7377)
- **Daniel Julian**

Developed with the radiotherapy unit of CHD Castelluccio, Ajaccio, and the
University of Corsica.

## Licence

Released under the [MIT licence](LICENSE).
