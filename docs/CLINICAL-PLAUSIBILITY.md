# Clinical plausibility checks

The tests in `tests/` are internal: they establish that the software solves its
own equations. This document asks a different question. Randomised trials have
compared fractionations directly, so schedules a trial found non-inferior should
come out close in equivalent dose, and those it did not should not.

**This is a coherence check, not a clinical validation.** Non-inferiority in a
trial depends on the population, the dosimetry, the volumes, the margins, the
imaging and the systemic treatment, none of which a fractionation model sees. A
trial arm agreeing with a model number is weak evidence; a trial arm disagreeing
with it is more informative, and both appear below.

Every value was recomputed with the released version, reference dose 2 Gy per
fraction. Prostate: α/β = 3.1 Gy, dt = 6.2 Gy. Spinal cord: α/β = 2 Gy,
dt = 4 Gy, γ/α = 5.

## Target volume: prostate

| Trial | Schedule | EQD2 | Against | Trial outcome |
|---|---|---:|---:|---|
| HYPO-RT-PC | 42.7 Gy / 7 | 77.94 | 78.00 | non-inferior |
| CHHiP | 60 Gy / 20 | 72.46 | 74.00 | non-inferior |
| CHHiP | 57 Gy / 19 | 68.79 | 74.00 | not demonstrated |
| PROFIT | 60 Gy / 20 | 72.46 | 78.00 | non-inferior |
| PACE-B | 36.25 Gy / 5 | 73.34 | 76.12, 78.00 | non-inferior |

### HYPO-RT-PC — agreement to 0.06 Gy

42.7 Gy in seven fractions comes out at 77.94 Gy EQD2 against 78.00 Gy for the
conventional arm. The trial found 84 % failure-free survival in both arms at five
years, adjusted HR 1.002 (95 % CI 0.758–1.325), and 72 % against 65 % at ten
years, adjusted HR 0.84 (95 % CI 0.69–1.03).

This is the closest external agreement obtained. One caveat: 6.1 Gy < dt = 6.2 Gy,
so the case exercises the quadratic branch and the time correction, not the
linear tail.

### CHHiP — the ordering recovered

60 Gy in 20 fractions comes out 1.54 Gy below the conventional arm; the trial
reported 90.6 % against 88.3 % failure-free at five years, HR 0.84
(90 % CI 0.68–1.03), p<sub>NI</sub> = 0.0018.

57 Gy in 19 fractions comes out 5.21 Gy below; the trial reported 85.9 %,
HR 1.20 (90 % CI 0.99–1.46), p<sub>NI</sub> = 0.48 — non-inferiority was not
established.

The software orders the two hypofractionated arms as the trial did. Most CHHiP
patients received androgen suppression, which limits what the comparison carries
radiobiologically.

### PROFIT — a quantitative disagreement

The same 60 Gy in 20 fractions sits 5.54 Gy below 78 Gy in 39, yet PROFIT,
without hormone therapy, reported 85 % biochemical or clinical failure-free
survival in both arms, HR 0.96 (90 % CI 0.77–1.20), and demonstrated
non-inferiority.

This is not an arithmetic error but a sensitivity to α/β. Under the plain
linear-quadratic form with α/β = 1.5 Gy:

```
EQD2 = 60 × (3 + 1.5) / (2 + 1.5) = 77.14 Gy
```

within a gray of the conventional arm. A pooled clinical estimate of
α/β = 1.4 Gy (0.9–2.2) has been published for prostate. **The tabulated 3.1 Gy
cannot be treated as universal.**

### PACE-B — the linear tail exercised

At 7.25 Gy per fraction the dose is above dt, so the linear tail applies:

```
BED_LQL = 5 × [6.2 × (1 + 6.2/3.1) + 5 × (7.25 − 6.2)] = 119.25 Gy_3.1
EQD2    = 119.25 / (1 + 2/3.1) = 72.49 Gy      (before the time correction)
```

and 73.34 Gy once the reference schedule carries its own overall time. That
places the stereotactic arm 2.78 Gy below 62 Gy in 20 and 4.66 Gy below 78 Gy in
39, while the trial reported 95.8 % against 94.6 % failure-free at five years,
HR 0.73 (90 % CI 0.48–1.12), p<sub>NI</sub> = 0.004. The linear tail predicts a
lower EQD2 under this parameterisation; that is a statement about the model, not
a demonstration of clinical prudence.

## Organ at risk: spinal cord

### Stereotactic, 25.3 Gy in five fractions

HyTEC associates a maximum dose of 25.3 Gy in five fractions with a 1–5 % risk of
radiation myelopathy. At 5.06 Gy per fraction:

```
BED_LQL = 5 × [4 × (1 + 4/2) + 5 × (5.06 − 4)] = 86.50 Gy_2
EQD2    = 86.50 / (1 + 2/2) = 43.25 Gy
```

against 44.65 Gy under the plain linear-quadratic form, a difference of −1.40 Gy
(−3.1 %). The reported complication probability is 1.45 %, numerically inside the
HyTEC range.

That agreement should not be pressed: HyTEC defines its constraint on a maximum
dose to the cord or thecal sac, and the software has no volume information at
all.

### Conventional, 50 Gy in 25 fractions — the library fails

The equivalent dose is exactly 50.00 Gy, as it must be at the reference fraction
size. The reported complication probability is **5.13 %**.

QUANTEC puts the risk of myelopathy near **0.2 %** at 50 Gy, 1 % at 54 Gy and
10 % at 61 Gy in conventional fractionation. The discrepancy is an order of
magnitude. It does not touch the equivalent dose: it is a property of the
tabulated Lyman parameters. The same failure has been reported clinically — the
Lyman-Kutcher-Burman model with historical parameters does not predict spinal
cord tolerance in radiosurgery.

## What this establishes

The equivalent doses are internally coherent and externally plausible: agreement
to 0.06 Gy with HYPO-RT-PC, the correct ordering of the two CHHiP arms, and a
stereotactic cord calculation consistent with HyTEC.

Two limits are equally clear:

1. **One prostate α/β of 3.1 Gy understates by about 5 Gy** the equivalence
   PROFIT demonstrated. 1.5 Gy would have placed the arms within a gray.
2. **The conventional spinal cord complication curve is incompatible with
   QUANTEC** by an order of magnitude.

No arithmetic defect is identified in the equivalent doses. The fixed
radiobiological library, however, **cannot be presented as clinically
validated**. The weaker point is the calibration of the complication parameters;
after it, the use of one prostate α/β for every case. Both are why the
complication and control probabilities are reported as indicative.

## References

- Widmark A, *et al.* HYPO-RT-PC 5-year outcomes. *Lancet* 2019;394:385–95.
  [10.1016/S0140-6736(19)31131-6](https://doi.org/10.1016/S0140-6736(19)31131-6)
- Nilsson P, *et al.* HYPO-RT-PC 10-year outcomes. *Lancet Oncol*
  2026;27:293–301.
  [10.1016/S1470-2045(25)00656-4](https://doi.org/10.1016/S1470-2045(25)00656-4)
- Dearnaley D, *et al.* CHHiP 5-year outcomes. *Lancet Oncol* 2016;17:1047–60.
  [10.1016/S1470-2045(16)30102-4](https://doi.org/10.1016/S1470-2045(16)30102-4)
- Catton CN, *et al.* PROFIT. *J Clin Oncol* 2017;35:1884–90.
  [10.1200/JCO.2016.71.7397](https://doi.org/10.1200/JCO.2016.71.7397)
- van As N, *et al.* PACE-B. *N Engl J Med* 2024;391:1413–25.
  [10.1056/NEJMoa2403365](https://doi.org/10.1056/NEJMoa2403365)
- Miralbell R, *et al.* Prostate α/β = 1.4 (0.9–2.2) Gy. *Int J Radiat Oncol Biol
  Phys* 2012;82:e17–24.
  [10.1016/j.ijrobp.2010.10.075](https://doi.org/10.1016/j.ijrobp.2010.10.075)
- Sahgal A, *et al.* Spinal cord dose tolerance to SBRT (HyTEC). *Int J Radiat
  Oncol Biol Phys* 2021;110:124–36.
  [10.1016/j.ijrobp.2019.09.038](https://doi.org/10.1016/j.ijrobp.2019.09.038)
- Kirkpatrick JP, *et al.* Radiation dose-volume effects in the spinal cord
  (QUANTEC). *Int J Radiat Oncol Biol Phys* 2010;76:S42–9.
  [10.1016/j.ijrobp.2009.04.095](https://doi.org/10.1016/j.ijrobp.2009.04.095)
- Daly ME, *et al.* LKB does not predict spinal cord tolerance to radiosurgery.
  *Int J Radiat Oncol Biol Phys* 2012;82:2025–32.
  [10.1016/j.ijrobp.2011.03.004](https://doi.org/10.1016/j.ijrobp.2011.03.004)
