"""The radiobiological library shipped with the 2014 application.

Thirty-four organs at risk and nineteen tumour sites, transcribed from the
``if/elseif`` chains of ``eqd_matlb.m``. The values are the ones the 2014
application *computes* with; where its own interface displayed something else,
the discrepancy is recorded in :data:`DISPLAY_MISMATCHES_2014`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True)
class Tissue:
    """One entry of the radiobiological library.

    Attributes
    ----------
    index:
        Position in the 2014 application's drop-down list. Kept so that results
        can be traced back to the original software.
    alpha_beta:
        :math:`\\alpha/\\beta` ratio, in gray.
    alpha:
        :math:`\\alpha` coefficient of the linear-quadratic model, in Gy^-1.
    Tk:
        Kick-off time of accelerated proliferation, in days.
    Tp:
        Effective doubling time during proliferation, in days.
    dt:
        Transition dose at which the linear-quadratic model gives way to the
        linear tail, in gray. Equal to :math:`2\\,\\alpha/\\beta` throughout the
        shipped library.
    T_half:
        Half-time of sublethal damage repair, in hours.
    dprol:
        Dose consumed per day by proliferation, in Gy/day. Tabulated for organs
        at risk; derived from ``alpha`` and ``Tp`` for tumours.
    m, d50:
        Dose-response parameters. Their meaning differs by tissue type, which is
        why the 2014 application could not use both with a single formula:

        * for an **organ at risk**, ``m`` is the Lyman probit slope (0.075 to
          0.27 across the shipped library) and ``d50`` the dose producing a 50 %
          *complication* rate, in gray;
        * for a **tumour**, ``m`` is the normalised slope :math:`\\gamma_{50}`
          (0.28 to 3.38 across the shipped library, far outside any plausible
          Lyman range) and ``d50`` is the TCD50, the dose producing 50 % *tumour
          control*. Use :attr:`gamma50` and :attr:`tcd50` when reading them in
          that role.
    puns, alpha2:
        Coefficients of the radiation-induced cancer risk model. ``puns`` of zero
        means no risk estimate is available for this tissue.
    """

    index: int
    name: str
    name_fr: str
    alpha_beta: float
    alpha: float
    Tk: float
    Tp: float
    dt: float
    T_half: float
    endpoint: str = ""
    endpoint_fr: str = ""
    dprol: float = 0.0
    #: Tumours only: proliferation dose given explicitly instead of being derived
    #: from ``alpha`` and ``Tp``. ``None`` means derive it; ``0.0`` means this
    #: tumour genuinely does not proliferate.
    dprol_override: float | None = None
    m: float = 0.0
    d50: float = 0.0
    puns: float = 0.0
    alpha2: float = 0.0
    #: Empty for the 34 organs and 19 tumours of the 2014 release; otherwise a
    #: note saying where the entry comes from.
    source: str = ""

    @property
    def gamma50(self) -> float:
        """Normalised dose-response slope, for a tumour. Alias of ``m``."""
        return self.m

    @property
    def tcd50(self) -> float:
        """Dose giving 50 % tumour control, in gray. Alias of ``d50``."""
        return self.d50

    @property
    def has_ntcp(self) -> bool:
        """Whether a complication probability can be estimated for this tissue.

        Meaningful for organs at risk only: complication probability is a
        normal-tissue quantity. Tumours use :attr:`has_tcp`.
        """
        return self.m > 0.0 and self.d50 > 0.0

    @property
    def has_tcp(self) -> bool:
        """Whether a tumour control probability can be estimated for this tumour."""
        return self.gamma50 > 0.0 and self.tcd50 > 0.0

    @property
    def is_from_2014_release(self) -> bool:
        """Whether this entry is one of the originals, unchanged."""
        return not self.source

    @property
    def has_cancer_risk(self) -> bool:
        """Whether a radiation-induced cancer risk can be estimated."""
        return self.puns > 0.0


@dataclass(frozen=True)
class DisplayMismatch:
    """A place where the 2014 interface showed a value it did not compute with."""

    kind: str
    index: int
    name: str
    parameter: str
    displayed_2014: float
    used_2014: float


@dataclass(frozen=True)
class Library:
    """The full shipped library."""

    oar: tuple[Tissue, ...] = field(default_factory=tuple)
    tumour: tuple[Tissue, ...] = field(default_factory=tuple)
    gamma_over_alpha: float = 5.0
    mismatches: tuple[DisplayMismatch, ...] = field(default_factory=tuple)

    def organ(self, name_or_index: str | int) -> Tissue:
        """Look an organ at risk up by name or by its 2014 drop-down index."""
        return _lookup(self.oar, name_or_index, "organ at risk")

    def tumour_site(self, name_or_index: str | int) -> Tissue:
        """Look a tumour up by name or by its 2014 drop-down index."""
        return _lookup(self.tumour, name_or_index, "tumour")

    @property
    def organ_names(self) -> list[str]:
        return [t.name for t in self.oar]

    @property
    def tumour_names(self) -> list[str]:
        return [t.name for t in self.tumour]


def _lookup(items: tuple[Tissue, ...], key: str | int, what: str) -> Tissue:
    for item in items:
        if key == item.index or key == item.name:
            return item
    raise KeyError(f"unknown {what}: {key!r}")


def _tissue(entry: dict) -> Tissue:
    fields = {f for f in Tissue.__dataclass_fields__}
    return Tissue(**{k: v for k, v in entry.items() if k in fields})


@lru_cache(maxsize=1)
def load_library() -> Library:
    """Load and cache the shipped radiobiological library."""
    with resources.files("lqlequiv.data").joinpath("tissues.json").open(
        "r", encoding="utf-8"
    ) as handle:
        raw = json.load(handle)
    return Library(
        oar=tuple(_tissue(e) for e in raw["oar"]),
        tumour=tuple(_tissue(e) for e in raw["tumour"]),
        gamma_over_alpha=raw["gamma_over_alpha"],
        mismatches=tuple(
            DisplayMismatch(**m) for m in raw.get("display_mismatches_2014", [])
        ),
    )


#: Parameters the 2014 interface displayed incorrectly. See the comparison document.
DISPLAY_MISMATCHES_2014 = load_library().mismatches
