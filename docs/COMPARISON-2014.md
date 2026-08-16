# LQL-Equiv 3.0 against the 2014 MATLAB release

This document quantifies the difference between this implementation and the
original application, names the defects the reimplementation uncovered in that
original, and lists the improvement axes.

## The 2014 release

| | |
| --- | --- |
| Repository | [`cyrilvoyant/LQ-Equiv`](https://github.com/cyrilvoyant/LQ-Equiv) |
| Software DOI | [10.5281/zenodo.16739883](https://doi.org/10.5281/zenodo.16739883) |
| Methodology paper | Voyant C, Julian D, Roustit R, Biffi K, Lantieri C. *Rep Pract Oncol Radiother* 2014;19(1):47–55, [doi:10.1016/j.rpor.2013.08.004](https://doi.org/10.1016/j.rpor.2013.08.004) |
| Implementation | MATLAB GUIDE application, `eqd_matlb.m`, 3 567 lines, plus a compiled `LQL-Equiv.exe` |
| Distribution | Windows executable requiring the MATLAB Component Runtime |

The entire calculation lives in one callback, `pushbutton4_Callback`. The
radiobiological library is written out as inline `if/elseif` chains; the
equivalent fraction count is found by evaluating an objective at every point of
a grid of hundredths of a fraction and taking the minimum.

## How the comparison was made

The 2014 GUIDE application still runs under MATLAB R2025b and can be driven
without a display: the figure is opened invisibly, the input fields are set, the
callbacks are invoked in the order the interface would invoke them, and the
output fields are read back. [`tools/matlab/sweep.m`](../tools/matlab/sweep.m)
does this over **4 438 treatment schedules**:

- every organ-at-risk × tumour pair (646 cases) on a 25 × 2 Gy schedule;
- a wide fractionation grid on two representative pairs — dose per fraction from
  1.2 to 20 Gy, 1 to 100 fractions, gaps of 0, 7 and 14 days, one and two
  fractions a day (3 192 cases);
- 600 randomised two- and three-course schedules.

Its outputs are stored verbatim in [`tests/data/golden.jsonl`](../tests/data/golden.jsonl)
and replayed by [`tools/compare_with_2014.py`](../tools/compare_with_2014.py).

**Resolution limit.** MATLAB writes its interface fields through `num2str`,
which emits six significant digits. That is the finest resolution at which the
two implementations can be compared at all; a residual below it means the two
agree as far as the captured data can tell.

## Result

| Quantity | Compared | Max deviation | Mean deviation |
| --- | ---: | ---: | ---: |
| Total equivalent dose, organ at risk (Gy) | 3 800 | 4.8 × 10⁻⁴ | 1.7 × 10⁻⁵ |
| Total equivalent dose, tumour (Gy) | 3 990 | 4.0 × 10⁻² | 2.0 × 10⁻⁵ |
| Complication probability (%) | 4 288 | 5.0 × 10⁻⁵ | 3.6 × 10⁻⁶ |
| Radiation-induced cancer risk | 3 797 | 5.0 × 10⁻⁶ | 1.8 × 10⁻⁷ |
| Equivalent dose per course, organ at risk (Gy) | 13 314 | 4.8 × 10⁻⁴ | 5.6 × 10⁻⁶ |
| Equivalent dose per course, tumour (Gy) | 13 314 | 2.0 × 10⁻² | 6.0 × 10⁻⁶ |
| BED per course, organ at risk (Gy) | 13 314 | 4.9 × 10⁻³ | 6.8 × 10⁻⁵ |
| BED per course, tumour (Gy) | 13 314 | 4.9 × 10⁻³ | 1.5 × 10⁻⁴ |

Counted at MATLAB's own output precision:

| | |
| --- | --- |
| Values compared | 69 131 |
| **Agreeing** | **69 125 (99.9913 %)** |
| Values differing | 6 |
| **Cases affected** | **2 of 4 438 (0.05 %)** |

### The two remaining cases

Both are exact ties. In the worst one — small bowel, rectum tumour, 7 × 3 Gy
then 8 × 1.8 Gy then 9 × 1.5 Gy — the true root sits at 11.375 reference
fractions, precisely halfway between the grid points 11.37 and 11.38. The two
residuals are:

```
grid 1137  residual = 0.012000000000004007
grid 1138  residual = 0.011999999999996902
```

They are mathematically equal; the ordering of floating-point operations decides
which one `min` returns, and MATLAB's ordering differs from Python's. The
consequence is a 0.02 Gy shift in an equivalent dose — below any resolution the
model itself possesses. Reproducing it would require emulating MATLAB's
expression evaluation bit for bit, which is not a defensible engineering goal.

### The search method is separately proved equivalent

The original scans 20 001 grid points; this implementation solves the objective
in closed form and scores only the grid points around each root. That shortcut
is legitimate only if it lands on the same point every time — which is not
obvious, because proliferation switching on at the kick-off time makes the tumour
objective piecewise linear, so it can approach the target twice and its best
grid point can sit next to the kink rather than next to a root.

[`tools/verify_grid_equivalence.py`](../tools/verify_grid_equivalence.py) settles
this by replaying the full grid for every case:

```
10 554 searches replayed against the full grid
0 disagreement(s)
```

This check does not depend on the MATLAB outputs at all.

## Defects found in the 2014 release

All four are reproduced by default; each has a switch or an explicit report.

### 1. Tumour control probability was never computed

The library carries a dose-response slope and a 50 % dose for eleven tumour
sites. No code path reads them. They are not Lyman parameters — the slopes run
from 0.28 to 3.38, whereas the organ-at-risk Lyman slopes span 0.075 to 0.27 —
so they are γ50 and TCD50 values of a tumour control curve, and could not be fed
to the probit that was coded. This is very probably why they were left unused.
Version 3.0 computes the TCP from them.

### 2. Nine parameters were displayed differently from those used

The interface fills its parameter listbox from hand-typed strings, independent of
the numeric table the computation reads. Seven tissues disagree:

| Tissue | Parameter | Displayed | Used |
| --- | --- | ---: | ---: |
| Heart | α | 0.579 | 0.0579 |
| Colon | T½ | 5 | 2 |
| Small bowel | Tp | 0.4 | 5 |
| Eye | α/β | 2.9 | 2 |
| Eye | T½ | 4 | 2 |
| Eye | transition dose | 5.8 | 4 |
| Skin (acute) | T½ | 1.2 | 2.1 |
| Medulloblastoma | transition dose | 4 | 16 |
| Prostate | T½ | 1.9 | 1.5 |

The eye's three displayed values are mutually consistent — its shown transition
dose is exactly twice its shown α/β — which points to a display block copied
from a different tissue rather than three independent typos. The computation was
never affected; only what the user was told. The list is carried in the data file
and asserted by the test-suite.

### 3. The calendar model contradicts itself past 86 fractions

Overall treatment time is obtained from a seventeen-step staircase converting
fractions to calendar days. The staircase is written out twice, and the two
copies differ in their fallback branch once past the last step at 86 fractions:
the interface copy floors the result, the computation copy does not. At exactly
86 × 2 Gy the equivalent dose comes out as 172.12 Gy where it should be 172.

The staircase has a closed form that reproduces all seventeen steps and extends
past 86 fractions continuously; enabling it removes the inconsistency. It is off
by default and has no effect below 86 fractions.

### 4. Complication probability was fabricated for tissues that have none

Five tissues carry no Lyman parameters. The 2014 code divides by zero and
displays 100 %, indistinguishable from a genuine certainty of complication.
Version 3.0 reports the quantity as unavailable.

### 5. Three time conventions the published equations do not describe

Found in August 2026, after an independent review read the source against the
manuscript. These are not rounding differences: they change the answer.

| | 2014 source, reproduced by `Convention.LEGACY` | Published equations, solved by `Convention.CORRECTED` |
|---|---|---|
| Organ proliferation | flat `n * 7/5 * dprol`, `Tk` never read | `dprol * (T - Tk)+`, as for the tumour |
| Reported organ dose | `n_r * d_r - (T - T_r) * dprol` | `n_r * d_r` |
| Tumour calendar | flat `(n + g) * 7/5`, blind to the weekend staircase and to two fractions a day | one absolute calendar at 7 days per 5 sessions, shared by both tissues |

The second is the largest. For a rectum receiving 20 × 3 Gy, `n_r * d_r` is
75.03 Gy while 82.69 Gy is reported: a second time correction is applied on top
of a root that already carried one. Two consequences follow. Splitting a
40-fraction course into two courses of 20 adds 0.6 Gy from nowhere, because the
weekend staircase restarts and `Θ(40) = 54` against `2 Θ(20) = 52`. And an organ
whose proliferation begins on day 100 is charged as though it began on day one.

`LEGACY` remains the library default, so results published before 2026 stay
reproducible, and it is what the 4438-schedule golden suite measures. `CORRECTED`
is what the browser application runs. Four tests in `tests/test_analytic.py`
separate them, each failing under `LEGACY` by construction. The corrected
convention uses the continuous rate 7/5 rather than the integer staircase on both
sides of the equality, because a staircase is not additive and cannot be inverted
on the real-valued fraction count; the staircase is still reported as the nominal
calendar.

## Improvement axes

**Delivered in 3.0**

- Runs in a browser or as a Python library; no MATLAB, no runtime, no Windows.
- Tumour control probability, from parameters that were already present.
- Complication probability reported as unavailable instead of fabricated.
- Every parameter's provenance recorded ([`docs/PARAMETERS.md`](PARAMETERS.md)).
- A 4 438-case non-regression suite, and a proof that the fast search matches the
  original exhaustive one.
- English interface; the 2014 release was French-only, which limited its reach.
- Isoeffect curves and a therapeutic-window plot, instead of isolated point values.
- Scenario comparison with CSV and JSON export.

**Candidates for later**

- Sensitivity bands on α/β, which is the dominant source of uncertainty.
- Tolerance-dose checking against the per-organ constraints the 2014 interface
  displayed but never tested against.
- An updated parameter set drawn from the post-2014 literature, kept alongside
  the historical one rather than replacing it.
- A shareable permalink encoding a scenario, for citation in papers.
