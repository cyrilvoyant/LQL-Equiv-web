"""LQL-Equiv: biologically equivalent doses in radiotherapy.

A Python port of the 2014 MATLAB application ``cyrilvoyant/LQ-Equiv``, computing
biologically effective dose, equivalent dose in a reference fractionation,
normal-tissue complication probability, tumour control probability and
radiation-induced cancer risk under the linear-quadratic-linear model.

**For research and education only. Not intended for clinical use.** This
software is not a medical device.

Example
-------
>>> from lqlequiv import Course, Prescription, compute, load_library
>>> library = load_library()
>>> plan = Prescription(courses=(Course(2.0, 39),), reference_dose=2.0)
>>> result = compute(library.organ("Rectum"), library.tumour_site("Prostate"), plan)
>>> round(result.eqd_oar_total, 2)
78.0
"""

from .model import (
    Course,
    CourseResult,
    Options,
    Prescription,
    Result,
    TCPModel,
    TimeModel,
    compute,
    normal_tissue_complication_probability,
    radiation_induced_cancer_risk,
    tumour_control_probability,
)
from .schedule import course_days, overall_time
from .tissues import Library, Tissue, load_library

__version__ = "3.0.0"

__all__ = [
    "Course",
    "CourseResult",
    "Library",
    "Options",
    "Prescription",
    "Result",
    "TCPModel",
    "TimeModel",
    "Tissue",
    "__version__",
    "compute",
    "course_days",
    "load_library",
    "normal_tissue_complication_probability",
    "overall_time",
    "radiation_induced_cancer_risk",
    "tumour_control_probability",
]
