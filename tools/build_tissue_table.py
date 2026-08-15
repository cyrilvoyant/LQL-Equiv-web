"""Build ``src/lqlequiv/data/tissues.json`` from the original MATLAB source.

The 2014 application stores its radiobiological library as inline ``if/elseif``
branches inside ``pushbutton4_Callback`` (numeric values, used for the
computation) and as pre-formatted listbox strings inside the two popup-menu
callbacks (what the user actually sees). This script reads the numeric branches,
attaches the English tissue names, and records the places where the displayed
values disagree with the computed ones.

Usage::

    python tools/build_tissue_table.py path/to/eqd_matlb.m path/to/menus.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# --- English names, keyed by the 1-based popup index used by the MATLAB app ---

OAR_EN = {
    2: "Temporomandibular joint", 3: "Rib cage", 4: "Oral cavity / oropharynx",
    5: "Brain", 6: "Optic chiasm", 7: "Heart", 8: "Colon", 9: "Stomach",
    10: "Liver", 11: "Small bowel", 12: "Larynx / supraglottis",
    13: "Spinal cord", 14: "Oral mucosa", 15: "Muscle / vasculature / cartilage",
    16: "Optic nerve", 17: "Eye", 18: "Oesophagus", 19: "Middle / external ear",
    20: "Parotid", 21: "Skin (acute)", 22: "Skin (late)", 23: "Brachial plexus",
    24: "Lung", 25: "Cauda equina", 26: "Rectum", 27: "Kidney", 28: "Retina",
    29: "Testis", 30: "Femoral head", 31: "Thyroid", 32: "Brainstem",
    33: "Bladder", 34: "Standard acute-responding tissue",
    35: "Standard late-responding tissue",
}

TUMOUR_EN = {
    2: "Tonsil", 3: "Carcinoma", 4: "Cervix (LQ-L)", 5: "Vocal cord",
    6: "Glioblastoma (LQ-L)", 7: "Larynx", 8: "Liposarcoma",
    9: "Medulloblastoma (LQ-L)", 10: "Oral mucosa", 11: "Nasopharynx",
    12: "Oesophagus", 13: "Oropharynx", 14: "Skin carcinoma",
    15: "Skin melanoma (LQ-L)", 16: "Lung", 17: "Prostate", 18: "Rectum",
    19: "Breast carcinoma", 20: "Standard tumour",
}

ENDPOINT_EN = {
    "Limitation articulation": "Joint restriction",
    "Fracture": "Fracture",
    "N\xe9crose du cartilage": "Cartilage necrosis",
    "N\xe9crose c\xe9r\xe9brale": "Brain necrosis",
    "c\xe9cit\xe9": "Blindness",
    "C\xe9cit\xe9": "Blindness",
    "P\xe9ricardite": "Pericarditis",
    "Ulc\xe9ration, fistule": "Ulceration, fistula",
    "Ulc\xe9ration, perforation": "Ulceration, perforation",
    "Troubles fonctionnels": "Functional impairment",
    "Perforation": "Perforation",
    "Oed\xe8me": "Oedema",
    "Myelite": "Myelitis",
    "Non utilisable": "Not applicable",
    "Otite chronique": "Chronic otitis",
    "X\xe9rostomie": "Xerostomia",
    "Eryth\xe8me": "Erythema",
    "N\xe9crose": "Necrosis",
    # "Troules" is a typo for "Troubles" in the 2014 source; kept as the key.
    "Troules n\xe9vralgiques": "Neuralgia",
    "Pneumopathie": "Pneumonitis",
    "Rectite": "Proctitis",
    "N\xe9phrite": "Nephritis",
    "St\xe9rilit\xe9": "Sterility",
    "Thyroidite": "Thyroiditis",
    "Trouble de la r\xe9pl\xe9tion": "Impaired bladder filling",
    "Cataracte": "Cataract",
    "St\xe9rilisation": "Sterilisation",
    "Pas assez de donn\xe9es cliniques": "Insufficient clinical data",
    "Choisir un OAR": "",
    "Choisir un VC": "",
}

# MATLAB field name -> name used in the Python package.
OAR_FIELDS = {
    "alphab": "alpha_beta", "alpha": "alpha", "Tk": "Tk", "Tp": "Tp",
    "dt": "dt", "T12": "T_half", "dprol": "dprol", "m": "m", "d50": "d50",
    "puns": "puns", "alpha2": "alpha2",
}
TUMOUR_FIELDS = {
    "alphabt": "alpha_beta", "alphat": "alpha", "Tkt": "Tk", "Tpt": "Tp",
    "dtt": "dt", "T12t": "T_half", "mt": "m", "d50t": "d50",
}

# Displayed-vs-computed disagreements found in the 2014 source. Recorded here so
# the comparison document and the test-suite can assert they are still known.
DISPLAY_KEY = {"a/b": "alpha_beta", "a": "alpha", "T1/2": "T_half",
               "Tk": "Tk", "Tp": "Tp", "Dprol": "dprol", "Dt": "dt"}


def _branches(text: str, selector: str) -> dict[int, dict]:
    """Return ``{popup_index: {matlab_name: value}}`` for one ``if/elseif`` chain."""
    out: dict[int, dict] = {}
    pattern = r"\b%s\s*==\s*(\d+)\s*\n(.*?)(?=\n\s*(?:elseif|else\b|end\b))" % selector
    for match in re.finditer(pattern, text, re.DOTALL):
        body = match.group(2)
        params: dict[str, object] = {}
        for assign in re.finditer(r"(\w+)\s*=\s*('([^']*)'|-?[\d.]+)", body):
            name, raw, string = assign.group(1), assign.group(2), assign.group(3)
            params[name] = string if string is not None else float(raw)
        if params:
            out[int(match.group(1))] = params
    return out


def _displayed(text: str, selector: str) -> dict[int, dict[str, float]]:
    """Return the numbers the GUI *shows* in its listbox, per popup index."""
    out: dict[int, dict[str, float]] = {}
    pattern = r"\(?%s\s*==\s*(\d+)\)?\s*\n(.*?)(?=\n\s*(?:elseif|else\b|end\b))" % selector
    for match in re.finditer(pattern, text, re.DOTALL):
        shown: dict[str, float] = {}
        for line in re.findall(r"'([^']*)'", match.group(2)):
            item = re.match(r"\s*([\w/]+)\s*=\s*(-?\d+(?:[.,]\d+)?)", line)
            if item and item.group(1) in DISPLAY_KEY:
                # The listbox strings use French decimal commas.
                shown[DISPLAY_KEY[item.group(1)]] = float(item.group(2).replace(",", "."))
        if shown:
            out[int(match.group(1))] = shown
    return out


def build(source: Path, menus: Path) -> dict:
    text = source.read_text(encoding="latin-1")
    names = json.loads(menus.read_text(encoding="utf-8"))

    numeric = {"oar": _branches(text, "sain"), "tumour": _branches(text, "tum")}
    shown = {"oar": _displayed(text, "sain1"), "tumour": _displayed(text, "tum1")}
    fields = {"oar": OAR_FIELDS, "tumour": TUMOUR_FIELDS}
    english = {"oar": OAR_EN, "tumour": TUMOUR_EN}
    endpoint_key = {"oar": "endpoint", "tumour": "endpointt"}
    menu_key = {"oar": "oar", "tumour": "tumor"}

    table: dict[str, list] = {"oar": [], "tumour": []}
    mismatches: list[dict] = []

    for kind in ("oar", "tumour"):
        for index in sorted(numeric[kind]):
            raw = numeric[kind][index]
            entry = {
                "index": index,
                "name": english[kind][index],
                "name_fr": names[menu_key[kind]][index - 1],
                "endpoint": ENDPOINT_EN.get(str(raw.get(endpoint_key[kind], "")), ""),
                "endpoint_fr": raw.get(endpoint_key[kind], ""),
            }
            for matlab_name, py_name in fields[kind].items():
                if matlab_name in raw:
                    entry[py_name] = raw[matlab_name]
            entry.setdefault("m", 0.0)
            entry.setdefault("d50", 0.0)
            table[kind].append(entry)

            for py_name, displayed_value in shown[kind].get(index, {}).items():
                if py_name in entry and abs(float(entry[py_name]) - displayed_value) > 1e-9:
                    mismatches.append({
                        "kind": kind, "index": index, "name": entry["name"],
                        "parameter": py_name,
                        "displayed_2014": displayed_value,
                        "used_2014": entry[py_name],
                    })

    return {
        "_comment": (
            "Radiobiological parameters transcribed from the 2014 MATLAB source "
            "(cyrilvoyant/LQ-Equiv, eqd_matlb.m). Values are the ones the 2014 "
            "application actually computes with."
        ),
        "gamma_over_alpha": 5.0,  # `ya` / `yat` in the MATLAB source
        "oar": table["oar"],
        "tumour": table["tumour"],
        "display_mismatches_2014": mismatches,
    }


def main() -> int:
    source = Path(sys.argv[1])
    menus = Path(sys.argv[2])
    data = build(source, menus)
    out = Path(__file__).resolve().parent.parent / "src" / "lqlequiv" / "data" / "tissues.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"  {len(data['oar'])} organs at risk, {len(data['tumour'])} tumours")
    print(f"  {len(data['display_mismatches_2014'])} displayed-vs-computed mismatches recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
