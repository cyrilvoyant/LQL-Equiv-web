"""Cross-check that every citation in the manuscript resolves in the bibliography."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    tex = (HERE / "main.tex").read_text(encoding="utf-8")
    bib = (HERE / "refs.bib").read_text(encoding="utf-8")

    cited: set[str] = set()
    for group in re.findall(r"\\cite\{([^}]*)\}", tex):
        cited.update(key.strip() for key in group.split(","))
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))

    missing = sorted(cited - keys)
    unused = sorted(keys - cited)
    print(f"citations in main.tex : {len(cited)}")
    print(f"entries in refs.bib   : {len(keys)}")
    print(f"cited but missing     : {missing or 'none'}")
    print(f"present but uncited   : {len(unused)}")
    for key in unused:
        print(f"    {key}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
