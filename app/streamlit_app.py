"""LQL-Equiv web interface.

A calculation interface for biologically equivalent doses in radiotherapy,
built on the :mod:`lqlequiv` package. Research and education only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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

STYLE = """
<style>
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


def main() -> None:
    st.set_page_config(page_title="LQL-Equiv", page_icon="◐", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    library = load_library()

    st.title("LQL-Equiv")
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
    unit = f"Gy (EQD{reference_dose:g})"
    columns = st.columns(4)
    columns[0].metric(
        f"Equivalent dose — {oar.name}",
        "not computable" if not result.oar_total_valid
        else f"{result.eqd_oar_total:.2f}",
        help=f"Cumulative equivalent dose to the organ at risk, in {unit}.",
    )
    columns[1].metric(
        f"Equivalent dose — {tum.name}",
        "not computable" if not result.tumour_total_valid
        else f"{result.eqd_tumour_total:.2f}",
        help=f"Cumulative equivalent dose to the tumour, in {unit}.",
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
            "BED organ (Gy)": row.bed_oar,
            "EQD organ (Gy)": row.eqd_oar,
            "BED tumour (Gy)": row.bed_tumour,
            "EQD tumour (Gy)": row.eqd_tumour,
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

    with isoeffect_tab:
        st.markdown("Equivalent dose against the number of fractions of the first "
                    "course, all else held equal.")
        rows = []
        for count in range(1, 61):
            probe = compute(oar, tum, Prescription(
                courses=(Course(course1.dose_per_fraction, count, course1.gap_days),
                         course2, course3),
                reference_dose=reference_dose, bifractionated=bifractionated,
            ), options, library)
            rows.append({"Fractions": count,
                         oar.name: probe.eqd_oar_total,
                         tum.name: probe.eqd_tumour_total})
        st.line_chart(pd.DataFrame(rows).set_index("Fractions"))

    with window_tab:
        st.markdown(
            "Tumour against organ-at-risk equivalent dose as the dose per fraction "
            "varies at constant total physical dose. Points above the diagonal "
            "favour the tumour."
        )
        total = course1.total_dose
        rows = []
        if total > 0:
            for tenths in range(10, 101, 2):
                dose = tenths / 10.0
                probe = compute(oar, tum, Prescription(
                    courses=(Course(dose, total / dose, course1.gap_days),
                             course2, course3),
                    reference_dose=reference_dose, bifractionated=bifractionated,
                ), options, library)
                rows.append({"Dose per fraction (Gy)": dose,
                             "Organ at risk (Gy)": probe.eqd_oar_total,
                             "Tumour (Gy)": probe.eqd_tumour_total})
            frame = pd.DataFrame(rows)
            st.scatter_chart(frame, x="Organ at risk (Gy)", y="Tumour (Gy)",
                             color="Dose per fraction (Gy)")
            st.caption(f"Total physical dose held at {total:.4g} Gy.")
        else:
            st.info("Enter a first course to draw the therapeutic window.")

    with scenario_tab:
        name = st.text_input("Scenario name", value=f"{course1.n_fractions:g} × "
                                                   f"{course1.dose_per_fraction:g} Gy")
        if st.button("Save this scenario", type="primary"):
            st.session_state.setdefault("scenarios", []).append({
                "Scenario": name, "Organ at risk": oar.name, "Tumour": tum.name,
                "Reference (Gy)": reference_dose,
                "EQD organ (Gy)": None if not result.oar_total_valid else result.eqd_oar_total,
                "EQD tumour (Gy)": None if not result.tumour_total_valid else result.eqd_tumour_total,
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
        st.markdown("#### Contributors")
        for person in CONTRIBUTORS:
            st.markdown(f"- **{person}**")
        st.markdown("#### References")
        for text, url in REFERENCES:
            st.markdown(f"- {text} [{url}]({url})")
        st.markdown("#### Licence")
        st.markdown(
            "Released under the MIT licence. The radiobiological library is "
            "transcribed from the 2014 release; see `docs/PARAMETERS.md` for the "
            "provenance of every value, and `docs/COMPARISON-2014.md` for the "
            "quantified comparison against the original MATLAB application."
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
