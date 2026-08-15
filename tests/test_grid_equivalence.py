"""The closed-form search must land on the 2014 grid point, every time.

This is the test that justifies replacing the exhaustive search of the original
application by a closed-form one. It replays the full grid of 20001 points for
every case of the golden dataset, so it is slow and needs numpy.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy")

from verify_grid_equivalence import verify  # noqa: E402


@pytest.mark.slow
def test_closed_form_agrees_with_exhaustive_grid(golden_path):
    assert verify(golden_path) == 0
