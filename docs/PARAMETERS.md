# Radiobiological parameters and their provenance

The shipped library holds 34 organs at risk and 19 tumour sites. This document
records where every value comes from and what is known about it.

**Rule followed throughout this file: no value and no citation appears here
unless it was verified against the source. Where no updated published source has
been identified for a tissue, the 2014 value is kept and that is stated
explicitly rather than filled with a plausible-looking number.**

## The shipped set: `voyant2014`

Source: the inline `if/elseif` chains of `pushbutton4_Callback` in `eqd_matlb.m`,
from [`cyrilvoyant/LQ-Equiv`](https://github.com/cyrilvoyant/LQ-Equiv)
([10.5281/zenodo.16739883](https://doi.org/10.5281/zenodo.16739883)), transcribed
mechanically by [`tools/build_tissue_table.py`](../tools/build_tissue_table.py)
rather than by hand.

The parameters as published are described in:

> Voyant C, Julian D, Roustit R, Biffi K, Lantieri C. Biological effects and
> equivalent doses in radiotherapy: a software solution. *Reports of Practical
> Oncology and Radiotherapy* 2014;19(1):47–55.
> [doi:10.1016/j.rpor.2013.08.004](https://doi.org/10.1016/j.rpor.2013.08.004)

### Meaning of each field

| Field | Organ at risk | Tumour |
| --- | --- | --- |
| `alpha_beta` | α/β ratio, Gy | same |
| `alpha` | α of the linear-quadratic model, Gy⁻¹ | same |
| `Tk` | repopulation kick-off time, days | same |
| `Tp` | effective doubling time during repopulation, days | same |
| `dt` | transition dose to the linear tail, Gy — equal to 2 α/β throughout | same |
| `T_half` | sublethal damage repair half-time, hours | same |
| `dprol` | dose consumed per day by repopulation, Gy/day — tabulated | derived as 0.693 / (α · Tp), except two sites where it is fixed at 0.3 |
| `m` | **Lyman probit slope** (0.075 to 0.27) | **γ50, normalised slope of the control curve** (0.28 to 3.38) |
| `d50` | dose giving 50 % complication, Gy | TCD50, dose giving 50 % control, Gy |
| `puns`, `alpha2` | radiation-induced cancer risk coefficients | not used |

The `m`/`d50` pair carries a different meaning on each side. This is not a
convention chosen here: the magnitudes make it unavoidable, and it explains why
the 2014 application, which had a single Lyman formula, loaded the tumour pair
and never used it. See [`COMPARISON-2014.md`](COMPARISON-2014.md).

### Known defects in this set

Nine parameters were *displayed* by the 2014 interface with values differing from
those it *computed* with, across seven tissues. The computed values are the ones
kept here; the full list is carried in the data file under
`display_mismatches_2014` and tabulated in [`COMPARISON-2014.md`](COMPARISON-2014.md).

### Likely upstream origin of the Lyman parameters

The organ-at-risk `m` and `d50` values fall within the range of the fits that
Burman and colleagues published for the Emami tolerance compilation, which is
almost certainly their origin, though the 2014 paper does not cite them
value-by-value:

> Burman C, Kutcher GJ, Emami B, Goitein M. Fitting of normal tissue tolerance
> data to an analytic function. *Int J Radiat Oncol Biol Phys*
> 1991;21(1):123–135. [PMID 2032883](https://pubmed.ncbi.nlm.nih.gov/2032883/)

> Emami B, Lyman J, Brown A, *et al.* Tolerance of normal tissue to therapeutic
> irradiation. *Int J Radiat Oncol Biol Phys* 1991;21(1):109–122.

This attribution is stated as **probable, not established**. It has not been
verified value by value, and no value has been altered on the strength of it.

## Alternative sets

None are shipped yet. The loader accepts additional sets so that an updated
library can be selected without replacing the historical one — reproducing the
2014 results must remain possible.

Two sources have been identified and verified as suitable starting points:

> van Leeuwen CM, Oei AL, Crezee J, Bel A, Franken NAP, Stalpers LJA, Kok HP.
> The alfa and beta of tumours: a review of parameters of the linear-quadratic
> model, derived from clinical radiotherapy studies. *Radiation Oncology*
> 2018;13(1):96. [doi:10.1186/s13014-018-1040-z](https://doi.org/10.1186/s13014-018-1040-z)
> — open access; a systematic review of clinically derived tumour α, β and α/β.

> Marks LB, Yorke ED, Jackson A, *et al.* Use of normal tissue complication
> probability models in the clinic. *Int J Radiat Oncol Biol Phys*
> 2010;76(3 Suppl):S10–S19. — the QUANTEC update of the Emami tolerances.

Transcription from these will be done by reading the papers, one value at a
time, each carrying its own citation in the data file. Until that is done, no
partial or approximate alternative set is shipped.

## Adding a parameter set

Each entry must carry a `source` field naming author, year, journal and DOI. A
set may be partial: tissues it does not cover fall back to `voyant2014`, and the
fallback is reported in the interface rather than hidden.
