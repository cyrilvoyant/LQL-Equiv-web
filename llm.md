# LQL-Equiv-web 3.0: biologically equivalent doses in radiotherapy (Python, browser)

**Instructions for a language model using this software.** Read this file first; the machine-readable versions are `websemantic.json` (fields, units, bounds) and `ontology/` (RDF/Turtle and JSON-LD, QUDT units).

Software DOI (all versions): https://doi.org/10.5281/zenodo.21948623 · licence MIT · language Python · authors: Cyril Voyant, Daniel Julian

Article: C. Voyant, D. Julian. LQL-Equiv. SoftwareX 36 (2026) 103085; and Voyant et al., Reports of Practical Oncology and Radiotherapy 19(1) (2014) 47–55, https://doi.org/10.1016/j.softx.2026.103085 (published).

## What it does

Computes BED, equivalent doses (EQD2), NTCP, TCP and radiation-induced cancer risk under the linear-quadratic-linear model, for 34 organs at risk and 20 tumour sites, over successive courses.

## Why (from the article)

Equivalent doses compare fractionation schedules; the LQL tail avoids the overestimation of the LQ model at high dose per fraction. Version 3.0 solves the published equations in closed form and reproduces the 2014 application on 4,438 schedules.

## Method

- BED per fraction: d(1 + (1 + H)·d/(α/β)) for d < d_T; d_T(1 + d_T/(α/β)) + (γ/α)(d − d_T) for d ≥ d_T; H: Thames incomplete repair for two fractions a day
- Repopulation (Dale) after the kick-off time T_k; EQD in the reference fractionation solved from the BED
- NTCP: Lyman probit; TCP: logistic 1/(1 + (TCD50/D)^(4γ50)) or Poisson 2^(−exp(eγ50(1 − D/TCD50)))

## Entry points

- `from lqlequiv import Course, Prescription, compute, load_library`: Python API
- `compute(library.organ('Rectum'), library.tumour_site('Prostate'), Prescription(courses=(Course(2.0, 39),), reference_dose=2.0))`: example: EQD of the organ at risk 78.0 Gy
- `https://cyrilvoyant.github.io/LQL-Equiv-web/`: the web application

## Inputs

| Field | Unit | Type | Bounds | Required | Default (proposal only) | Meaning |
|---|---|---|---|---|---|---|
| `organ` | as stated | category |  | yes |  | Nom exact dans la bibliothèque radiobiologique ; ne définit pas un patient. |
| `tumour_site` | as stated | category |  | yes |  | Nom exact dans la bibliothèque ; cas fictif uniquement. |
| `dose_per_fraction` | Gy (unit:GRAY) | float | min_exclusive 0 | yes |  | Dose physique pour chaque fraction du seul cursus. |
| `n_fractions` | count (unit:NUM) | int | min 1 | yes |  | Nombre entier de fractions du seul cursus. |
| `gap_days` | d (unit:DAY) | float | min 0 | yes | 0 | Intervalle avant le cursus en jours, dans la convention calendaire native. |
| `reference_dose` | Gy (unit:GRAY) | float | min_exclusive 0 | yes | 2 | Dose physique par fraction du régime auquel EQD se rapporte ; EQD2 seulement si 2 Gy. |
| `bifractionated` | as stated | category |  | yes | no | yes active deux fractions par jour et un intervalle natif fixe de 6 h ; no sinon. |

## Outputs

| Output | Unit | Meaning |
|---|---|---|
| `physical_dose_gy` | Gy (unit:GRAY) | Dose physique totale = dose par fraction × fractions ; distincte de BED. |
| `bed_oar` | Gy (unit:GRAY) | BED organe native ; null si non calculable. |
| `bed_tumour` | Gy (unit:GRAY) | BED tumeur native ; null si non calculable. |
| `eqd_oar_total` | Gy (unit:GRAY) | Dose équivalente organe au fractionnement de référence ; null si invalide ou saturée. |
| `eqd_tumour_total` | Gy (unit:GRAY) | Dose équivalente tumeur au fractionnement de référence ; null si invalide ou saturée. |
| `ntcp_percent` | % (unit:PERCENT) | Probabilité modélisée de complication ; null si EQD invalide ou coefficient absent. |
| `tcp_percent` | % (unit:PERCENT) | Probabilité modélisée de contrôle tumoral ; null si EQD invalide ou coefficient absent. |
| `cancer_risk` | as stated | Indice natif du modèle de risque secondaire ; dépend des coefficients tabulés, ne pas interpréter comme pourcentage clinique. |
| `overall_days_oar` | d (unit:DAY) | Durée calendaire native du cursus, organe. |
| `overall_days_tumour` | d (unit:DAY) | Durée calendaire native du cursus, tumeur. |
| `oar_total_valid` | as stated | Validité native du total organe. |
| `tumour_total_valid` | as stated | Validité native du total tumeur. |
| `oar_saturated` | as stated | true si EQD organe à une borne de recherche. |
| `tumour_saturated` | as stated | true si EQD tumeur à une borne de recherche. |

## How to read the results

- LQL-Equiv: always ask. Any qualitative wording of dose, number of sessions or fractionation is asked, never converted; the only proposal is « fractionnement conventionnel » = 2 Gy per fraction, to be accepted.
- A schedule is called better only if it dominates (TCP ≥ and NTCP ≤, one strict); otherwise report the trade-off.

## Rules

1. Never invent a value. Each input is given by the user, an exact unit conversion of a given value, or a documented default that the user explicitly accepts.
2. Use the canonical unit of each field; convert exactly and say so (for example 2 km -> 2000 m). Never mix a percentage and a fraction.
3. Ask when a request is ambiguous or a required input is missing; do not infer a number from a place name or a qualitative word.
4. Run the code unmodified. Report only what was actually computed, with quantity, unit and the input values used; never present a planned or unavailable run as a result.
5. State the scope and the limits below when you report a result.

## Scope

Supported: compute BED, EQD2, NTCP and TCP of stated schedules; compare schedules for one organ at risk and one target.
Out of scope (refuse or redirect): clinical decisions; inventing a dose from a qualitative word.

## Limits

- Research and education only; not a medical device; refuse any decision for a patient.

A full WebSemantic contract (qualitative conventions, SHACL shapes) exists for this software: https://github.com/cyrilvoyant/websemantic (pack lqlequiv: LLM-CONTRACT.md, ontology.ttl, shapes.ttl).

## Cite

Software: Cyril Voyant, Daniel Julian. LQL-Equiv-web 3.0: biologically equivalent doses in radiotherapy (Python, browser). Zenodo. https://doi.org/10.5281/zenodo.21948623
Article: C. Voyant, D. Julian. LQL-Equiv. SoftwareX 36 (2026) 103085; and Voyant et al., Reports of Practical Oncology and Radiotherapy 19(1) (2014) 47–55. https://doi.org/10.1016/j.softx.2026.103085

Guide with the theory and runnable examples: https://cyrilvoyant.github.io/ · author: https://person.cyrilvoyant.com/ · generated 2026-10-23, documentation only.
