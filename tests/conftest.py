"""Shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

GOLDEN = ROOT / "tests" / "data" / "golden.jsonl"


@pytest.fixture(scope="session")
def golden_path() -> Path:
    if not GOLDEN.exists():
        pytest.skip("golden dataset not present")
    return GOLDEN
