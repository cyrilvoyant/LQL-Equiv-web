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

### 5. The organ equivalent dose does not satisfy the equality it comes from

Found in August 2026, when an independent review read the source against the
paper it was published with. This is not a rounding difference.

The paper defines the equivalent dose in its equation (12) as `EQD2 = 2 n0`,
where `n0` minimises the cost function of equation (11). The source solves for
`n0` — with proliferation charged on both sides, at the rate `7/5` — and then
reports something else:

```matlab
EQDs2 = I2*0.01*dose1 - (eta2-eta1)*dprol;   % organ,  eqd_matlb.m line 3245
EQDt2 = It2*0.01*dose1;                       % target, line 3276
```

`eta2` is the overall time of the schedule and `eta1` that of its equivalent,
both from the weekend staircase. The subtraction charges the difference in span a
second time, the root having already balanced it.

**The test.** An equivalent dose has one defining property: delivered at the
reference fraction size, it must reproduce the biologically effective dose it
replaced. For a rectum (α/β = 3.9 Gy, `dprol` = 0.3 Gy/day) receiving 20 × 3 Gy:

| | 2014 | version 3.0 |
|---|---|---|
| BED of the schedule | 97.75 Gy | 97.75 Gy |
| equivalent dose reported | 82.69 Gy | 75.25 Gy |
| as fractions of 2 Gy | 41.34 | 37.63 |
| BED of *that* schedule | **107.74 Gy** | **97.75 Gy** |
| round trip closes | no, +9.97 Gy | yes, 0.00 Gy |

Over 7850 deliverable schedules the round trip closes for 28.6 % of the 2014
values and for all of version 3.0's. Splitting a 40-fraction course into two
courses of 20 also moved the 2014 total by 0.6 Gy, the staircase restarting at
each course with `Θ(40) = 54` against `2 Θ(20) = 52`; version 3.0 is additive.

Of the 7.65 Gy the second term adds for this case, 7.36 Gy is the span already
priced into `n0` and 0.30 Gy is a genuine refinement, from replacing the rate
`7/5` by the real calendar. Version 3.0 keeps the refinement and drops the
duplicate: both sides of the equality now run on the staircase, since
proliferation is charged per elapsed day and weekends are elapsed days.

**What is not changed.** The two tissues keep the two proliferation models the
paper gives them. Equations (3) and (4) apply Dale to the target, with the
kick-off time `Tk`. Equations (6) and (7) apply Van Dyk to the organ at risk,
where — in the paper's words — *"the kick-off time is no longer considered, with
the recovered dose being added instead"*. `Tk` is therefore read for the target
and not for the organ, deliberately, and a test asserts both directions.

`Options.legacy_2014()` reproduces the 2014 behaviour, for recomputing a result
published before 2026 and for the 4438-schedule non-regression suite. Nothing
else in the software uses it.

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
