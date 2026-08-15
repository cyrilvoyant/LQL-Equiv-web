"""Word count of the manuscript, section by section.

Strips LaTeX commands, maths, verbatim blocks and tables, so that the figure is
comparable to what a journal counts rather than to what ``wc -w`` sees.
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def strip(text: str) -> str:
    text = re.sub(r"(?m)%.*$", "", text)                     # comments
    text = re.sub(r"\\begin\{verbatim\}.*?\\end\{verbatim\}", " ", text, flags=re.S)
    text = re.sub(r"\\begin\{(table|tabular|center)\}.*?"
                  r"\\end\{\1\}", " ", text, flags=re.S)
    text = re.sub(r"\\begin\{equation\}.*?\\end\{equation\}", " EQ ", text, flags=re.S)
    text = re.sub(r"\$[^$]*\$", " x ", text)                 # inline maths
    text = re.sub(r"\\includegraphics(\[[^\]]*\])?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(cite|ref|eqref|label|url|ead)\{[^}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", text)
    text = re.sub(r"[{}~\\]", " ", text)
    return text


def words(text: str) -> int:
    return len([w for w in strip(text).split() if any(c.isalnum() for c in w)])


def main() -> int:
    tex = (HERE / "main.tex").read_text(encoding="utf-8")

    body = tex.split(r"\end{frontmatter}", 1)[1]
    body = body.split(r"\bibliographystyle", 1)[0]

    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    print(f"{'abstract':<34}{words(abstract.group(1)) if abstract else 0:>6}")

    parts = re.split(r"\\section\*?\{([^}]*)\}", body)
    for name, chunk in zip(parts[1::2], parts[2::2]):
        total = words(chunk)
        print(f"{name:<34}{total:>6}")
        for sub, piece in zip(*[re.split(r"\\subsection\{([^}]*)\}", chunk)[1::2],
                                re.split(r"\\subsection\{([^}]*)\}", chunk)[2::2]]
                              if r"\subsection{" in chunk else ([], [])):
            print(f"    {sub:<30}{words(piece):>6}")
    print("-" * 40)
    print(f"{'body total (excl. refs, tables)':<34}{words(body):>6}")

    print()
    print(f"equations   {len(re.findall(r'\\begin{equation}', tex)):>3}")
    print(f"figures     {len(re.findall(r'\\begin{figure}', tex)):>3}")
    print(f"tables      {len(re.findall(r'\\begin{table}', tex)):>3}")
    print(f"citations   {len(set(k.strip() for g in re.findall(r'\\cite\{([^}]*)\}', tex) for k in g.split(','))):>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
