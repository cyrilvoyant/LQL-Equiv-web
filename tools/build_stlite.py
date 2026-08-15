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

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>LQL-Equiv &mdash; biologically equivalent doses in radiotherapy</title>
<meta name="description" content="Biologically equivalent doses in radiotherapy under the
 linear-quadratic-linear model: BED, EQD2, NTCP, TCP and radiation-induced cancer risk.
 Research and education only." />
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
  <h1>LQL-Equiv</h1>
  <div class="bar"><span></span></div>
  <p>Starting the Python runtime in your browser. The first load fetches it once and
     is then cached; nothing you enter leaves this page.</p>
  <p class="warn">For research and education only. Not intended for clinical use.</p>
</div>
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
    )
    out = ROOT / "web" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
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
