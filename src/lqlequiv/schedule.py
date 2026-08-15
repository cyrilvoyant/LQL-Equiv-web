"""Overall treatment time: the calendar model of the 2014 application.

Radiotherapy is delivered five days a week, so the elapsed calendar time of a
course is longer than its number of fractions. The 2014 MATLAB application
encodes that conversion as a seventeen-step staircase written out by hand, with
a ``* 7 / 5`` fallback once the staircase runs out at 86 fractions.

There are two variants of the staircase in the original source and they do not
agree with each other beyond the last step:

``overall_time``
    Used inside ``pushbutton4_Callback`` for the *reference* schedule. Its
    fallback is ``n * 7 / 5``.
``displayed_overall_time``
    Used by the ``edit*`` callbacks to fill the "etalement" field, which the
    same routine then reads back for the organ-at-risk equivalent dose. Its
    fallback is ``floor(n * 7 / 5)``.

Below 86 fractions the two agree exactly. At or above 86 they differ by up to
one day, which propagates into the organ-at-risk equivalent dose as an error of
up to ``0.4 * dprol`` gray. See ``docs/COMPARISON-2014.md``.

The staircase itself has a closed form that reproduces all seventeen steps and
extends past 86 fractions continuously, which is what ``STAIRCASE`` mode uses.
"""

from __future__ import annotations

import math
from enum import Enum

#: First step of the staircase: below six fractions no weekend has occurred yet.
_FIRST_STEP = 6
#: Fractions per step, and days added per step, after the first.
_STEP_WIDTH = 5
_DAYS_PER_STEP = 2
#: The 2014 staircase stops here and falls back to a plain 7/5 ratio.
LEGACY_LAST_STEP = 86


class TimeModel(str, Enum):
    """Which calendar model to use beyond the last hand-written step."""

    #: Reproduce the 2014 application exactly, fallback included.
    LEGACY = "legacy"
    #: Extend the staircase with its own closed form past 86 fractions.
    STAIRCASE = "staircase"


def _staircase_offset(n: float) -> float:
    """Days added to ``n`` fractions by intervening weekends."""
    if n < _FIRST_STEP:
        return 0.0
    return _DAYS_PER_STEP * (math.floor((n - _FIRST_STEP) / _STEP_WIDTH) + 1)


def overall_time(n: float, model: TimeModel = TimeModel.LEGACY) -> float:
    """Calendar days spanned by ``n`` fractions, reference-schedule variant.

    This is the staircase of ``pushbutton4_Callback``: no rounding is applied to
    the fallback branch.
    """
    if n < LEGACY_LAST_STEP or model is TimeModel.STAIRCASE:
        return n + _staircase_offset(n)
    return n * 7.0 / 5.0


def displayed_overall_time(n: float, model: TimeModel = TimeModel.LEGACY) -> float:
    """Calendar days spanned by ``n`` fractions, treatment-course variant.

    This is the staircase of the ``edit*`` callbacks. Its fallback branch floors
    the result, which is the sole reason the two variants disagree above 86
    fractions.
    """
    if n < LEGACY_LAST_STEP or model is TimeModel.STAIRCASE:
        return n + _staircase_offset(n)
    return float(math.floor(n * 7.0 / 5.0))


def course_days(
    n_fractions: float,
    gap_days: float = 0.0,
    bifractionated: bool = False,
    model: TimeModel = TimeModel.LEGACY,
) -> float:
    """Overall time of one treatment course, in days.

    Two fractions a day halve the number of treatment days. The 2014 source
    rounds an odd fraction count up (``floor(n / 2) + 1``) before adding the gap.
    """
    if not bifractionated:
        effective = n_fractions + gap_days
    elif n_fractions % 2 == 0:
        effective = n_fractions / 2.0 + gap_days
    else:
        effective = math.floor(n_fractions / 2.0) + 1.0 + gap_days
    return displayed_overall_time(effective, model)
