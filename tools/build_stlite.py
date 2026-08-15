"""Build the self-contained WebAssembly page served from GitHub Pages.

stlite runs Streamlit in the browser through Pyodide, so the application needs
no server at all. This script bundles the package sources, the radiobiological
library and the Streamlit entry point into a single ``web/index.html``.

The file contents are embedded as JSON and handed to stlite's ``mount()``
JavaScript API rather than written into ``<app-file>`` elements: the element
form runs the Python source through the HTML parser, where a ``<`` followed by
a letter starts a tag and silently corrupts the code.

Usage::

    python tools/build_stlite.py [--version 1.8.1]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Files copied into the virtual filesystem, as (source, destination) pairs.
BUNDLE = [
    ("app/streamlit_app.py", "streamlit_app.py"),
    ("src/lqlequiv/__init__.py", "lqlequiv/__init__.py"),
    ("src/lqlequiv/model.py", "lqlequiv/model.py"),
    ("src/lqlequiv/schedule.py", "lqlequiv/schedule.py"),
    ("src/lqlequiv/tissues.py", "lqlequiv/tissues.py"),
    ("src/lqlequiv/data/__init__.py", "lqlequiv/data/__init__.py"),
    ("src/lqlequiv/data/tissues.json", "lqlequiv/data/tissues.json"),
]

ENTRYPOINT = "streamlit_app.py"

#: Streamlit is bundled with stlite; the core package is pure standard library,
#: so nothing else has to be fetched at load time.
REQUIREMENTS: list[str] = []

CONFIG_TOML = """[client]
toolbarMode = "viewer"
showErrorDetails = false

[theme]
base = "light"
"""

SITE_URL = "https://cyrilvoyant.github.io/LQL-Equiv-web/"
REPO_URL = "https://github.com/cyrilvoyant/LQL-Equiv-web"

DESCRIPTION = (
    "Free online calculator for biologically equivalent doses in radiotherapy under the "
    "linear-quadratic-linear (LQL) model: biologically effective dose (BED), equivalent "
    "dose in 2 Gy fractions (EQD2), normal-tissue complication probability (NTCP), tumour "
    "control probability (TCP) and radiation-induced cancer risk. Runs entirely in your "
    "browser; no data is transmitted. For research and education only."
)

#: schema.org description of the software and the work it implements. Search
#: engines and language models read this in preference to parsing the page.
def _structured_data() -> str:
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "@id": SITE_URL + "#software",
                "name": "LQL-Equiv",
                "alternateName": ["LQL-Equiv-web", "LQ-Equiv", "LQL Equiv"],
                "applicationCategory": "HealthApplication",
                "applicationSubCategory": "Radiotherapy dose calculator",
                "operatingSystem": "Any (runs in a web browser)",
                "softwareVersion": "3.0.0",
                "url": SITE_URL,
                "codeRepository": REPO_URL,
                "programmingLanguage": "Python",
                "license": "https://opensource.org/licenses/MIT",
                "isAccessibleForFree": True,
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
                "description": DESCRIPTION,
                "featureList": [
                    "Biologically effective dose (BED) with the linear-quadratic-linear tail",
                    "Equivalent dose in 2 Gy fractions (EQD2) and any other reference fractionation",
                    "Normal-tissue complication probability (NTCP), Lyman probit model",
                    "Tumour control probability (TCP)",
                    "Radiation-induced cancer risk",
                    "Accelerated proliferation and incomplete inter-fraction repair",
                    "Any number of successive treatment courses, with treatment gaps",
                    "34 organs at risk and 20 tumour sites",
                ],
                "keywords": (
                    "radiotherapy, biologically effective dose, BED calculator, EQD2 "
                    "calculator, linear-quadratic-linear model, LQL, NTCP, TCP, "
                    "radiobiology, medical physics, fractionation, hypofractionation"
                ),
                "author": [
                    {
                        "@type": "Person",
                        "name": "Cyril Voyant",
                        "identifier": "https://orcid.org/0000-0003-0242-7377",
                        "url": "https://person.cyrilvoyant.com",
                        "email": "cyril.voyant@minesparis.psl.eu",
                        "affiliation": {
                            "@type": "Organization",
                            "name": "Mines Paris, PSL University",
                            "department": "Centre for Observation, Impacts, Energy (O.I.E.)",
                            "address": "Sophia-Antipolis, 06904, France",
                        },
                    },
                    {
                        "@type": "Person",
                        "name": "Daniel Julian",
                        "email": "Julian@ccgm.fr",
                        "affiliation": {
                            "@type": "Organization",
                            "name": "Centre de Cancerologie du Grand Montpellier",
                            "department": "Radiotherapy Unit",
                            "address": "Montpellier, 34000, France",
                        },
                    },
                ],
                "citation": [
                    {"@id": SITE_URL + "#paper2014"},
                    {"@id": SITE_URL + "#paper2017"},
                    {"@id": SITE_URL + "#paper2025"},
                ],
            },
            {
                "@type": "ScholarlyArticle",
                "@id": SITE_URL + "#paper2014",
                "name": ("Biological effects and equivalent doses in radiotherapy: "
                         "a software solution"),
                "datePublished": "2014",
                "isPartOf": {"@type": "Periodical",
                             "name": "Reports of Practical Oncology and Radiotherapy"},
                "identifier": "https://doi.org/10.1016/j.rpor.2013.08.004",
            },
            {
                "@type": "ScholarlyArticle",
                "@id": SITE_URL + "#paper2017",
                "name": ("A short synthesis concerning biological effects and "
                         "equivalent doses in radiotherapy"),
                "datePublished": "2017",
                "isPartOf": {"@type": "Periodical",
                             "name": "Journal of Radiology and Oncology"},
                "identifier": "https://doi.org/10.29328/journal.jro.1001005",
            },
            {
                "@type": "ScholarlyArticle",
                "@id": SITE_URL + "#paper2025",
                "name": ("Improving clinical decision-making in radiotherapy: a "
                         "comparative analysis of linear-quadratic (LQ) and "
                         "linear-quadratic-linear (LQL) dose models"),
                "datePublished": "2025",
                "isPartOf": {"@type": "Periodical", "name": "Clinical Oncology"},
                "identifier": "https://doi.org/10.1016/j.clon.2025.103893",
            },
            {
                "@type": "FAQPage",
                "@id": SITE_URL + "#faq",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": "What is the linear-quadratic-linear (LQL) model?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": ("The linear-quadratic model overestimates cell kill at "
                                     "high dose per fraction. The linear-quadratic-linear "
                                     "model of Astrahan replaces the quadratic term by a "
                                     "straight line above a transition dose, which makes it "
                                     "usable for the large fractions of stereotactic "
                                     "radiotherapy."),
                        },
                    },
                    {
                        "@type": "Question",
                        "name": "What is EQD2?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": ("EQD2 is the dose that, delivered in 2 Gy fractions, "
                                     "would produce the same biological effect as the "
                                     "schedule under consideration. It allows schedules with "
                                     "different fraction sizes to be compared."),
                        },
                    },
                    {
                        "@type": "Question",
                        "name": "Can LQL-Equiv be used clinically?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": ("No. LQL-Equiv is for research and education only. It is "
                                     "not a medical device and must not be used to plan, "
                                     "verify or modify the treatment of a patient."),
                        },
                    },
                    {
                        "@type": "Question",
                        "name": "Is any data sent to a server?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": ("No. The application runs entirely inside the browser "
                                     "through WebAssembly. Nothing that is entered leaves "
                                     "the machine."),
                        },
                    },
                ],
            },
        ],
    }
    return json.dumps(graph, ensure_ascii=False, indent=1)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>LQL-Equiv &mdash; BED, EQD2, NTCP and TCP calculator for radiotherapy</title>
<meta name="description" content="{description}" />
<meta name="author" content="Cyril Voyant, Daniel Julian" />
<meta name="keywords" content="radiotherapy, BED calculator, EQD2 calculator, biologically
 effective dose, linear-quadratic-linear model, LQL, NTCP, TCP, radiobiology, medical physics,
 fractionation, hypofractionation, equivalent dose" />
<link rel="canonical" href="{site}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="LQL-Equiv" />
<meta property="og:title" content="LQL-Equiv &mdash; biologically equivalent doses in radiotherapy" />
<meta property="og:description" content="{description}" />
<meta property="og:url" content="{site}" />
<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="LQL-Equiv &mdash; biologically equivalent doses in radiotherapy" />
<meta name="twitter:description" content="{description}" />
<script type="application/ld+json">{jsonld}</script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.css" />
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; }}
  #root {{ height: 100%; }}
  #boot {{
    position: fixed; inset: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 0.9rem;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    color: #1f2933; background: #ffffff; text-align: center; padding: 2rem;
  }}
  #boot h1 {{ font-size: 1.3rem; font-weight: 600; margin: 0; letter-spacing: -0.01em; }}
  #boot p {{ margin: 0; font-size: 0.87rem; color: #52606d; max-width: 30rem; line-height: 1.55; }}
  #boot .bar {{ width: 12rem; height: 3px; border-radius: 3px; background: #e4e7eb; overflow: hidden; }}
  #boot .bar span {{
    display: block; height: 100%; width: 40%; background: #3b6ea5;
    animation: slide 1.15s ease-in-out infinite;
  }}
  @keyframes slide {{ 0% {{ transform: translateX(-110%); }} 100% {{ transform: translateX(360%); }} }}
  #boot .warn {{ font-size: 0.78rem; color: #8a6d3b; }}
</style>
</head>
<body>
<div id="boot">
  <h1>LQL-Equiv &mdash; biologically equivalent doses in radiotherapy</h1>
  <div class="bar"><span></span></div>
  <p>Starting the Python runtime in your browser. The first load fetches it once and
     is then cached; nothing you enter leaves this page.</p>
  <p>Computes biologically effective dose (BED), equivalent dose in 2 Gy fractions
     (EQD2), normal-tissue complication probability (NTCP), tumour control probability
     (TCP) and radiation-induced cancer risk under the linear-quadratic-linear model,
     for 34 organs at risk and 20 tumour sites.</p>
  <p class="warn">For research and education only. Not intended for clinical use.</p>
</div>
<noscript>
  <h1>LQL-Equiv &mdash; biologically equivalent doses in radiotherapy</h1>
  <p>{description}</p>
  <p>This application needs JavaScript, because it runs Python in your browser through
     WebAssembly. The source code, the documentation and the validation dataset are
     available at <a href="{repo}">{repo}</a>.</p>
</noscript>
<div id="root"></div>
<script type="application/json" id="app-files">{files}</script>
<script type="module">
import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{version}/build/stlite.js";

const files = JSON.parse(document.getElementById("app-files").textContent);
mount(
  {{
    entrypoint: {entrypoint},
    files,
    requirements: {requirements},
  }},
  document.getElementById("root"),
);

// Clear the placeholder once Streamlit has painted something.
const boot = document.getElementById("boot");
const observer = new MutationObserver(() => {{
  if (document.querySelector('#root [data-testid="stAppViewContainer"]')) {{
    boot.remove();
    observer.disconnect();
  }}
}});
observer.observe(document.getElementById("root"), {{ childList: true, subtree: true }});
</script>
</body>
</html>
"""


def build(version: str) -> Path:
    files: dict[str, str] = {}
    for source, destination in BUNDLE:
        path = ROOT / source
        if not path.exists():
            raise SystemExit(f"missing bundled file: {source}")
        files[destination] = path.read_text(encoding="utf-8")
    files[".streamlit/config.toml"] = CONFIG_TOML

    html = TEMPLATE.format(
        version=version,
        # </script> inside the JSON payload would close the host element early.
        files=json.dumps(files, ensure_ascii=False).replace("</", "<\\/"),
        entrypoint=json.dumps(ENTRYPOINT),
        requirements=json.dumps(REQUIREMENTS),
        description=DESCRIPTION,
        site=SITE_URL,
        repo=REPO_URL,
        jsonld=_structured_data().replace("</", "<\\/"),
    )
    out = ROOT / "web" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    # Crawler hints, served alongside the page from the same directory.
    (out.parent / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8"
    )
    (out.parent / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}</loc><changefreq>monthly</changefreq>"
        "<priority>1.0</priority></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.8.1", help="@stlite/browser version to pin")
    args = parser.parse_args()
    out = build(args.version)
    size = out.stat().st_size
    print(f"wrote {out.relative_to(ROOT)} ({size / 1024:.1f} kB, stlite {args.version})")
    print(f"  {len(BUNDLE)} python/data files bundled, entrypoint {ENTRYPOINT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
