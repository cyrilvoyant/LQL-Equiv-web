"""LQL-Equiv web interface.

A calculation interface for biologically equivalent doses in radiotherapy,
built on the :mod:`lqlequiv` package. Research and education only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Allow running straight from a checkout, without installing the package.
_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from lqlequiv import __version__  # noqa: E402
from lqlequiv.model import (  # noqa: E402
    Course,
    Options,
    Prescription,
    TCPModel,
    TimeModel,
    compute,
)
from lqlequiv.tissues import load_library  # noqa: E402

CONTRIBUTORS = ["Cyril Voyant", "Daniel Julian"]

REPOSITORY_URL = "https://github.com/cyrilvoyant/LQL-Equiv-web"

SOFTWARE_CITATION = (
    "Voyant C, Julian D. LQL-Equiv: biologically equivalent doses in radiotherapy "
    "under the linear-quadratic-linear model. Version 3.0.0, 2026.\n"
    f"{REPOSITORY_URL}"
)

SOFTWARE_BIBTEX = """@software{voyant_lqlequiv_2026,
  author  = {Voyant, Cyril and Julian, Daniel},
  title   = {{LQL-Equiv}: biologically equivalent doses in radiotherapy
             under the linear-quadratic-linear model},
  version = {3.0.0},
  year    = {2026},
  url     = {https://github.com/cyrilvoyant/LQL-Equiv-web}
}"""

REFERENCES = [
    ("Voyant C, Julian D, Roustit R, Biffi K, Lantieri C. "
     "Biological effects and equivalent doses in radiotherapy: a software solution. "
     "*Reports of Practical Oncology and Radiotherapy* 2014;19(1):47-55.",
     "https://doi.org/10.1016/j.rpor.2013.08.004"),
    ("Voyant C, Julian D. "
     "A short synthesis concerning biological effects and equivalent doses in radiotherapy. "
     "*Journal of Radiology and Oncology* 2017;1:039-045.",
     "https://doi.org/10.29328/journal.jro.1001005"),
    ("Improving clinical decision-making in radiotherapy: a comparative analysis of "
     "linear-quadratic (LQ) and linear-quadratic-linear (LQL) dose models. "
     "*Clinical Oncology* 2025;45.",
     "https://doi.org/10.1016/j.clon.2025.103893"),
    ("LQ-Equiv, the original MATLAB application (2014). Software, archived on Zenodo.",
     "https://doi.org/10.5281/zenodo.16739883"),
]

# A DNA double helix struck by an ionising track: what the model is ultimately
# about. Icon only -- the wordmark and the tagline are HTML, so that they wrap
# instead of being clipped by the drawing's own box.
LOGO = """
<svg viewBox="0 0 58 40" role="img" aria-label="" focusable="false"
     width="58" height="40">
  <defs>
    <linearGradient id="lqlg" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0%" stop-color="#3b6ea5"/>
      <stop offset="100%" stop-color="#4aa3a3"/>
    </linearGradient>
  </defs>
  <g fill="none" stroke="url(#lqlg)" stroke-width="2.4" stroke-linecap="round">
    <path d="M4 20 C 12 6, 24 6, 32 20 C 40 34, 48 34, 52 20"/>
    <path d="M4 20 C 12 34, 24 34, 32 20 C 40 6, 48 6, 52 20"/>
  </g>
  <g stroke="url(#lqlg)" stroke-width="1.5" stroke-linecap="round" opacity="0.62">
    <line x1="11.5" y1="11.5" x2="11.5" y2="28.5"/>
    <line x1="18" y1="9.5" x2="18" y2="30.5"/>
    <line x1="24.5" y1="11.5" x2="24.5" y2="28.5"/>
    <line x1="35.5" y1="11.5" x2="35.5" y2="28.5"/>
  </g>
  <path d="M56 2 L48.5 9 L52.5 11 L45 18" fill="none" stroke="#d1495b"
        stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="43.5" cy="19.5" r="2.6" fill="#d1495b"/>
</svg>
"""

STYLE = """
<style>
  .lql-head {display: flex; align-items: center; gap: 0.85rem; flex-wrap: wrap;
             margin-bottom: 0.2rem;}
  .lql-head svg {flex: none;}
  .lql-name {min-width: 0;}
  .lql-word {font-size: 1.6rem; font-weight: 650; letter-spacing: -0.02em;
             line-height: 1.15;}
  .lql-ver {font-size: 1rem; font-weight: 500; opacity: 0.55;
            vertical-align: 0.28em; letter-spacing: 0;}
  .lql-tag {font-size: 0.86rem; opacity: 0.72; line-height: 1.45;}
  .lql-pitch {font-size: 0.9rem; line-height: 1.6;}
  .block-container {padding-top: 2.4rem; max-width: 1150px;}
  h1 {font-size: 1.65rem !important; font-weight: 600; letter-spacing: -0.01em;}
  h2 {font-size: 1.15rem !important; font-weight: 600; margin-top: 1.6rem;}
  h3 {font-size: 0.98rem !important; font-weight: 600;}
  [data-testid="stMetricValue"] {font-size: 1.45rem;}
  .lql-note {font-size: 0.82rem; opacity: 0.72; line-height: 1.5;}
  .lql-footer {font-size: 0.8rem; opacity: 0.7; line-height: 1.6;
               border-top: 1px solid rgba(128,128,128,0.25);
               margin-top: 2.5rem; padding-top: 1rem;}
</style>
"""


def _value_input(label: str, key: str, low: float, high: float, step: float,
                 default: float, use_sliders: bool, help_text: str = "") -> float:
    """One numeric input, rendered as a slider or a typed field."""
    if use_sliders:
        return st.slider(label, float(low), float(high), float(default),
                         step=float(step), key=key, help=help_text or None)
    return st.number_input(label, min_value=float(low), max_value=float(high),
                           value=float(default), step=float(step), key=key,
                           help=help_text or None)


def _course_inputs(position: int, use_sliders: bool, enabled: bool = True) -> Course:
    """Dose per fraction, fraction count and preceding gap for one course."""
    if not enabled:
        return Course(0.0, 0.0, 0.0)
    left, middle, right = st.columns(3)
    with left:
        dose = _value_input("Dose per fraction (Gy)", f"d{position}", 0.0, 30.0, 0.1,
                            2.0 if position == 1 else 0.0, use_sliders)
    with middle:
        fractions = _value_input("Number of fractions", f"n{position}", 0.0, 100.0, 1.0,
                                 25.0 if position == 1 else 0.0, use_sliders)
    with right:
        gap = _value_input("Gap before this course (days)", f"g{position}", 0.0, 60.0, 1.0,
                           0.0, use_sliders,
                           "Treatment-free days between the previous course and this one.")
    st.caption(f"Total physical dose: **{dose * fractions:.4g} Gy**")
    return Course(dose, fractions, gap)


def _format(value: float | None, unit: str = "", digits: int = 2) -> str:
    if value is None:
        return "not available"
    return f"{value:.{digits}f}{unit}"


def _schedule_label(prescription: Prescription) -> str:
    """Render a prescription the way it is written on a chart: 5 x 2.2 Gy + 2 x 6.5 Gy."""
    parts = []
    for course in prescription.courses:
        if course.is_empty:
            continue
        piece = f"{course.n_fractions:g} × {course.dose_per_fraction:g} Gy"
        if course.gap_days:
            piece += f" (after {course.gap_days:g} d)"
        parts.append(piece)
    label = " + ".join(parts) if parts else "—"
    if prescription.bifractionated:
        label += ", 2/day"
    return label


def _fractions_matching_tumour_dose(
    target: float, dose: float, oar, tum, prescription, options, library,
    tolerance: float = 0.05,
) -> float | None:
    """Fractions of ``dose`` giving the same tumour equivalent dose as ``target``.

    Bisected on the fraction count, which the tumour equivalent dose increases
    with. A coarse scan is not good enough here: stepping the fraction count by
    half a fraction leaves most fraction sizes unable to reach the target at all,
    which punches holes in the curve.

    Returns ``None`` when no fraction count in range reaches the target.
    """
    def tumour_dose(count: float) -> float:
        return compute(oar, tum, Prescription(
            courses=(Course(dose, count, prescription.courses[0].gap_days),),
            reference_dose=prescription.reference_dose,
            bifractionated=prescription.bifractionated,
        ), options, library).eqd_tumour_total

    low, high = 0.1, 100.0
    if tumour_dose(low) > target or tumour_dose(high) < target:
        return None
    for _ in range(60):
        middle = (low + high) / 2
        if tumour_dose(middle) < target:
            low = middle
        else:
            high = middle
        if high - low < 1e-4:
            break
    count = (low + high) / 2
    return count if abs(tumour_dose(count) - target) <= tolerance else None


def main() -> None:
    st.set_page_config(page_title="LQL-Equiv", page_icon="◐", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    library = load_library()

    st.markdown(
        f"<div class='lql-head'>{LOGO}"
        "<div class='lql-name'>"
        "<div class='lql-word'>LQL-Equiv <span class='lql-ver'>3.0</span></div>"
        "<div class='lql-tag'>Equivalent doses in radiotherapy &middot; "
        "Cyril Voyant and Daniel Julian</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p class='lql-note'>Biologically equivalent doses in radiotherapy under the "
        "linear-quadratic-linear model &mdash; biologically effective dose, equivalent "
        "dose in a reference fractionation, normal-tissue complication probability, "
        "tumour control probability and radiation-induced cancer risk.</p>",
        unsafe_allow_html=True,
    )
    st.warning(
        "**For research and education only. Not intended for clinical use.** "
        "This software is not a medical device and must not be used to plan, verify "
        "or modify the treatment of a patient.",
        icon="⚠",
    )

    # ---------------------------------------------------------------- sidebar
    with st.sidebar:
        st.subheader("Tissues")
        organ = st.selectbox("Organ at risk", library.organ_names,
                             index=library.organ_names.index("Rectum"))
        tumour = st.selectbox("Tumour", library.tumour_names,
                              index=library.tumour_names.index("Prostate"))
        oar = library.organ(organ)
        tum = library.tumour_site(tumour)

        st.subheader("Reference schedule")
        reference_dose = st.number_input(
            "Reference dose per fraction (Gy)", 0.1, 20.0, 2.0, 0.1,
            help="Equivalent doses are expressed in this fractionation. "
                 "The conventional choice of 2 Gy gives EQD2.",
        )
        bifractionated = st.toggle(
            "Two fractions a day", value=False,
            help="Applies Thames' incomplete-repair correction, with a six-hour interval.",
        )

        st.subheader("Input style")
        use_sliders = st.radio(
            "Entry mode", ["Sliders", "Typed values"], horizontal=True,
            label_visibility="collapsed",
        ) == "Sliders"

        with st.expander("Model options"):
            legacy = st.toggle(
                "Reproduce the 2014 results exactly", value=True,
                help="Snaps the equivalent fraction count to the grid of one "
                     "hundredth of a fraction used by the 2014 application. "
                     "Turning this off returns the exact root instead, which "
                     "differs by at most 0.005 reference fractions.",
            )
            extend = st.toggle(
                "Extend the calendar staircase past 86 fractions", value=False,
                help="The 2014 calendar model is inconsistent with itself beyond "
                     "86 fractions. This replaces its fallback by the closed form "
                     "of the staircase. No effect below 86 fractions.",
            )
            tcp_choice = st.selectbox("Tumour control probability model",
                                      ["Logistic", "Poisson"])

        options = Options(
            legacy_quantisation=legacy,
            time_model=TimeModel.STAIRCASE if extend else TimeModel.LEGACY,
            tcp_model=TCPModel.LOGISTIC if tcp_choice == "Logistic" else TCPModel.POISSON,
        )

        with st.expander("Selected radiobiological parameters"):
            st.caption(f"**{oar.name}** — endpoint: {oar.endpoint or 'not applicable'}")
            st.dataframe(pd.DataFrame({
                "Parameter": ["α/β (Gy)", "α (Gy⁻¹)", "Tk (d)", "Tp (d)",
                              "Transition dose (Gy)", "T½ (h)", "Dprol (Gy/d)"],
                "Value": [oar.alpha_beta, oar.alpha, oar.Tk, oar.Tp,
                          oar.dt, oar.T_half, oar.dprol],
            }), hide_index=True, width="stretch")
            st.caption(f"**{tum.name}** — endpoint: {tum.endpoint or 'not applicable'}")
            st.dataframe(pd.DataFrame({
                "Parameter": ["α/β (Gy)", "α (Gy⁻¹)", "Tk (d)", "Tp (d)",
                              "Transition dose (Gy)", "T½ (h)"],
                "Value": [tum.alpha_beta, tum.alpha, tum.Tk, tum.Tp, tum.dt, tum.T_half],
            }), hide_index=True, width="stretch")

    # ----------------------------------------------------------------- inputs
    st.header("Treatment courses")
    course1 = _course_inputs(1, use_sliders)
    with st.expander("Second course"):
        use2 = st.checkbox("Add a second course", key="use2")
        course2 = _course_inputs(2, use_sliders, use2)
    with st.expander("Third course"):
        use3 = st.checkbox("Add a third course", key="use3", disabled=not use2)
        course3 = _course_inputs(3, use_sliders, use3 and use2)

    prescription = Prescription(
        courses=(course1, course2, course3),
        reference_dose=reference_dose,
        bifractionated=bifractionated,
    )
    result = compute(oar, tum, prescription, options, library)

    # ---------------------------------------------------------------- results
    st.header("Results")
    unit_gy = "Gy"
    unit = f"Gy EQD{reference_dose:g}"
    columns = st.columns(4)
    columns[0].metric(
        f"OAR — {oar.name}",
        "not computable" if not result.oar_total_valid
        else f"{result.eqd_oar_total:.2f} {unit_gy}",
        help=f"Cumulative equivalent dose to the organ at risk, in {unit}.",
    )
    columns[1].metric(
        f"Target — {tum.name}",
        "not computable" if not result.tumour_total_valid
        else f"{result.eqd_tumour_total:.2f} {unit_gy}",
        help=f"Cumulative equivalent dose to the target volume, in {unit}.",
    )
    columns[2].metric(
        "Complication probability",
        _format(result.ntcp_percent, " %"),
        help=f"Lyman probit NTCP for the endpoint: {oar.endpoint or 'none tabulated'}.",
    )
    columns[3].metric(
        "Tumour control probability",
        _format(result.tcp_percent, " %"),
        help="New in 3.0: computed from the tumour dose-response parameters that "
             "the 2014 application loaded but never used.",
    )

    if not result.oar_total_valid or not result.tumour_total_valid:
        st.info(
            "Two fractions a day combined with a dose above the linear-quadratic-linear "
            "transition dose falls outside the incomplete-repair model. The 2014 "
            "application printed “NC” here.",
            icon="ℹ",
        )
    if result.cancer_risk is not None:
        st.caption(f"Radiation-induced cancer risk coefficient: **{result.cancer_risk:.4g}**")
    else:
        st.caption("Radiation-induced cancer risk: no coefficient tabulated for this organ.")

    per_course = pd.DataFrame([
        {
            "Course": index,
            "Dose/fraction (Gy)": course.dose_per_fraction,
            "Fractions": course.n_fractions,
            "Gap (d)": course.gap_days,
            "Overall time (d)": row.overall_days_oar,
            "BED OAR (Gy)": row.bed_oar,
            f"EQD OAR ({unit_gy})": row.eqd_oar,
            "BED target (Gy)": row.bed_tumour,
            f"EQD target ({unit_gy})": row.eqd_tumour,
        }
        for index, (course, row) in enumerate(zip(prescription.courses, result.courses), 1)
        if not course.is_empty
    ])
    if not per_course.empty:
        st.dataframe(per_course.style.format(precision=3), hide_index=True,
                     width="stretch")

    # ------------------------------------------------------------------ tabs
    isoeffect_tab, window_tab, scenario_tab, about_tab = st.tabs(
        ["Isoeffect curves", "Therapeutic window", "Scenarios", "About"]
    )

    dose_axis = f"Equivalent dose ({unit})"

    with isoeffect_tab:
        st.markdown(
            "How the equivalent dose of the **first course** grows as it is "
            "lengthened, everything else held as entered. The vertical line marks "
            "the schedule currently entered."
        )
        sweep = st.radio(
            "Vary", ["Number of fractions", "Dose per fraction"],
            horizontal=True, key="isoeffect_axis",
        )
        rows = []
        if sweep == "Number of fractions":
            x_title, x_current = "Number of fractions", course1.n_fractions
            values = [n / 2 for n in range(2, 121)]
            def _course(v):
                return Course(course1.dose_per_fraction, v, course1.gap_days)
        else:
            x_title, x_current = f"Dose per fraction ({unit_gy})", course1.dose_per_fraction
            values = [d / 4 for d in range(4, 61)]
            def _course(v):
                return Course(v, course1.n_fractions, course1.gap_days)

        for value in values:
            probe = compute(oar, tum, Prescription(
                courses=(_course(value), course2, course3),
                reference_dose=reference_dose, bifractionated=bifractionated,
            ), options, library)
            rows.append({x_title: value, "Tissue": f"{oar.name} (OAR)",
                         dose_axis: probe.eqd_oar_total})
            rows.append({x_title: value, "Tissue": f"{tum.name} (target)",
                         dose_axis: probe.eqd_tumour_total})

        frame = pd.DataFrame(rows)
        curve = alt.Chart(frame).mark_line(strokeWidth=2).encode(
            x=alt.X(f"{x_title}:Q", title=x_title),
            y=alt.Y(f"{dose_axis}:Q", title=dose_axis),
            color=alt.Color("Tissue:N", title=None,
                            legend=alt.Legend(orient="top")),
            tooltip=[x_title, "Tissue", alt.Tooltip(f"{dose_axis}:Q", format=".2f")],
        )
        marker = alt.Chart(pd.DataFrame({x_title: [x_current]})).mark_rule(
            strokeDash=[4, 4], color="grey"
        ).encode(x=f"{x_title}:Q")
        st.altair_chart((curve + marker).properties(height=340), use_container_width=True)

    with window_tab:
        st.markdown(
            f"**Which fraction size reaches the same tumour effect at the lowest cost "
            f"to the {oar.name.lower()}?** The tumour equivalent dose is held at the "
            f"value of the schedule entered; for every fraction size the number of "
            f"fractions is adjusted to keep it there, and the resulting dose to the "
            f"organ at risk is plotted. The lowest point is the best fractionation "
            f"for that tumour effect."
        )
        target = result.eqd_tumour_total
        if target <= 0 or not result.tumour_total_valid:
            st.info("Enter a first course to draw the therapeutic window.")
        else:
            rows = []
            for step in range(2, 21):
                dose = step / 2.0
                count = _fractions_matching_tumour_dose(
                    target, dose, oar, tum, prescription, options, library
                )
                if count is None:
                    continue
                probe = compute(oar, tum, Prescription(
                    courses=(Course(dose, count, course1.gap_days),),
                    reference_dose=reference_dose, bifractionated=bifractionated,
                ), options, library)
                rows.append({
                    f"Dose per fraction ({unit_gy})": dose,
                    "Fractions": count,
                    f"Dose to the organ at risk ({unit})": probe.eqd_oar_total,
                    "Schedule": f"{count:.1f} × {dose:g} Gy",
                    "NTCP (%)": probe.ntcp_percent,
                })
            if not rows:
                st.info("No fractionation reproduces this tumour effect in the range "
                        "scanned. Try a different schedule.")
            else:
                frame = pd.DataFrame(rows)
                x_name = f"Dose per fraction ({unit_gy})"
                y_name = f"Dose to the organ at risk ({unit})"
                best = frame.loc[frame[y_name].idxmin()]
                chart = alt.Chart(frame).mark_line(point=True, strokeWidth=2).encode(
                    x=alt.X(f"{x_name}:Q", title=x_name),
                    y=alt.Y(f"{y_name}:Q", title=y_name,
                            scale=alt.Scale(zero=False)),
                    tooltip=["Schedule", alt.Tooltip(f"{y_name}:Q", format=".2f"),
                             alt.Tooltip("NTCP (%):Q", format=".2f")],
                )
                highlight = alt.Chart(pd.DataFrame([best])).mark_point(
                    size=180, color="crimson", filled=True
                ).encode(x=f"{x_name}:Q", y=f"{y_name}:Q")
                st.altair_chart((chart + highlight).properties(height=340),
                                use_container_width=True)
                complication = best["NTCP (%)"]
                st.success(
                    f"At a tumour equivalent dose of {target:.2f} {unit}, the least "
                    f"costly schedule scanned is **{best['Schedule']}**, giving "
                    f"**{best[y_name]:.2f} {unit}** to the {oar.name.lower()}"
                    + (f", for a {complication:.1f} % complication probability."
                       if complication is not None and pd.notna(complication) else ".")
                )
                at_edge = best[x_name] in (frame[x_name].min(), frame[x_name].max())
                if oar.dprol > 0 and at_edge:
                    st.warning(
                        f"The optimum sits at the edge of the range scanned, and "
                        f"{oar.name.lower()} carries a proliferation dose of "
                        f"{oar.dprol:g} Gy/day. Protracting treatment then *appears* to "
                        f"spare the organ at risk, because the model lets it proliferate "
                        f"too. That is a property of the model, not of late-responding "
                        f"normal tissue, and this optimum should not be read as a "
                        f"recommendation. Compare fraction sizes within a clinically "
                        f"plausible range instead."
                    )
                st.caption(
                    "Single course only, and a model comparison rather than a clinical "
                    "recommendation: it accounts for fraction size and overall time, "
                    "not for dose distribution, volume effects or the constraints of "
                    "any real plan."
                )

    with scenario_tab:
        schedule = _schedule_label(prescription)
        st.caption(f"Current schedule: **{schedule}**")
        name = st.text_input("Scenario name", value=schedule)
        if st.button("Save this scenario", type="primary"):
            st.session_state.setdefault("scenarios", []).append({
                "Scenario": name,
                "Schedule": schedule,
                "Total dose (Gy)": sum(c.total_dose for c in prescription.courses),
                "OAR": oar.name,
                "Target": tum.name,
                "Reference (Gy)": reference_dose,
                "EQD OAR (Gy)": None if not result.oar_total_valid else result.eqd_oar_total,
                "EQD target (Gy)": None if not result.tumour_total_valid else result.eqd_tumour_total,
                "NTCP (%)": result.ntcp_percent, "TCP (%)": result.tcp_percent,
            })
        saved = st.session_state.get("scenarios", [])
        if saved:
            frame = pd.DataFrame(saved)
            st.dataframe(frame.style.format(precision=3), hide_index=True,
                         width="stretch")
            left, right = st.columns(2)
            left.download_button("Download as CSV", frame.to_csv(index=False),
                                 "lql-equiv-scenarios.csv", "text/csv")
            right.download_button("Download as JSON", json.dumps(saved, indent=2),
                                  "lql-equiv-scenarios.json", "application/json")
            if st.button("Clear all scenarios"):
                st.session_state["scenarios"] = []
                st.rerun()
        else:
            st.caption("No scenario saved yet.")

    with about_tab:
        st.markdown("#### What it is for")
        st.markdown(
            "<p class='lql-pitch'>Comparing radiotherapy schedules that differ in "
            "fraction size, fraction number or overall time is not a matter of adding "
            "up physical dose: 20 × 3 Gy and 30 × 2 Gy are both 60 Gy and are not the "
            "same treatment. LQL-Equiv converts any schedule into the dose that would "
            "produce the same biological effect in a reference fractionation, for the "
            "target volume and for an organ at risk at the same time, and estimates "
            "the resulting complication and control probabilities.<br><br>"
            "It is built for teaching radiobiology, for designing and comparing "
            "schedules in protocol and research work, for re-irradiation questions "
            "where earlier courses have to be carried forward, and for sanity-checking "
            "equivalences by hand.</p>",
            unsafe_allow_html=True,
        )

        st.markdown("#### What it does that a plain BED calculator does not")
        st.markdown(
            "- **The linear-quadratic-linear model, not only the linear-quadratic one.** "
            "Above a transition dose the quadratic term is replaced by a straight line, "
            "so large fractions are not over-penalised. A pure LQ calculator "
            "systematically overstates the effect of stereotactic fraction sizes.\n"
            "- **Overall treatment time is modelled, not ignored.** Accelerated "
            "proliferation with a kick-off time, and treatment gaps. A ten-day "
            "interruption is worth about 12 Gy EQD2 on a fast-proliferating tumour; "
            "calculators that take only dose and fraction number cannot see that.\n"
            "- **Up to three successive courses**, each with its own fraction size and "
            "its own preceding gap, accumulated correctly — which is what a "
            "re-irradiation question actually needs.\n"
            "- **Two fractions a day**, with Thames' incomplete-repair correction.\n"
            "- **Organ at risk and target together**, plus NTCP and TCP, rather than a "
            "single number for a single tissue.\n"
            "- **A radiobiological library of 34 organs at risk and 20 target sites**, "
            "so the parameters do not have to be looked up and typed in.\n"
            "- **Traceable.** Open source under MIT, every parameter's provenance "
            "recorded, and validated against the published 2014 implementation over "
            "4438 schedules with the test data in the repository. Very few dose "
            "calculators can be checked at all.\n"
            "- **Private and free.** It runs inside your browser; nothing you enter is "
            "transmitted anywhere."
        )
        st.caption(
            "Model comparison only, and no substitute for a treatment planning system: "
            "it knows nothing of dose distribution, volume effects or plan constraints."
        )

        st.markdown("#### Contributors")
        for person in CONTRIBUTORS:
            st.markdown(f"- **{person}**")

        st.markdown("#### Citing this software")
        st.markdown(
            "If you use LQL-Equiv in academic work, please cite both the software "
            "and the methodology paper."
        )
        st.code(SOFTWARE_CITATION, language=None)
        st.caption("BibTeX")
        st.code(SOFTWARE_BIBTEX, language="bibtex")

        st.markdown("#### References")
        for text, url in REFERENCES:
            st.markdown(f"- {text} [{url}]({url})")

        st.markdown("#### Licence and provenance")
        st.markdown(
            "Released under the MIT licence. The radiobiological library is "
            "transcribed from the 2014 release; `docs/PARAMETERS.md` records the "
            "provenance of every value and `docs/COMPARISON-2014.md` the quantified "
            "comparison against the original MATLAB application. "
            f"[Source code and documentation]({REPOSITORY_URL})."
        )

    st.markdown(
        f"<p class='lql-footer'>LQL-Equiv {__version__} &middot; MIT licence &middot; "
        "research and education only, not a medical device &middot; "
        "successor to the 2014 MATLAB release "
        "<a href='https://github.com/cyrilvoyant/LQ-Equiv'>cyrilvoyant/LQ-Equiv</a>"
        "</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
