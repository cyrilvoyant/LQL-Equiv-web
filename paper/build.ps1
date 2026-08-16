# Build the manuscript and its supplementary material. Requires MiKTeX
# (winget install MiKTeX.MiKTeX).
#
#   pwsh paper/build.ps1
#
# Two documents are produced, and both go to the publisher:
#
#   main.pdf           the article
#   supplementary.pdf  the two analyses the article refers to, uploaded as a
#                      single supplementary file. Their content is also in
#                      docs/COMPARISON-2014.md and docs/CLINICAL-PLAUSIBILITY.md,
#                      for readers of the repository rather than of the journal.
#
# Four passes each: the first writes the .aux, BibTeX resolves the citations from
# it, and the last two settle the cross-references and the reference numbers.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command pdflatex -ErrorAction SilentlyContinue)) {
    throw "pdflatex not found. Install MiKTeX: winget install MiKTeX.MiKTeX"
}

Write-Host "regenerating figures and the numbers quoted in the text..."
python figures.py | Tee-Object -FilePath figures.log

$failed = $false

foreach ($doc in @("main", "supplementary")) {
    Write-Host ""
    Write-Host "=== $doc ==="
    & pdflatex -interaction=nonstopmode "$doc.tex" | Out-Null
    & bibtex $doc | Out-Null
    & pdflatex -interaction=nonstopmode "$doc.tex" | Out-Null
    & pdflatex -interaction=nonstopmode "$doc.tex" | Out-Null

    $log = Get-Content "$doc.log" -Raw
    $errors = ([regex]::Matches($log, '(?m)^! ')).Count
    $undefined = ([regex]::Matches($log, '(Citation|Reference) .* undefined')).Count
    $overfull = [regex]::Matches($log, 'Overfull \\hbox \(([\d.]+)pt') |
                ForEach-Object { [double]$_.Groups[1].Value }

    Write-Host "errors            : $errors"
    Write-Host "undefined refs    : $undefined"
    if ($overfull) {
        Write-Host ("overfull boxes    : {0} (worst {1:N1} pt)" -f $overfull.Count,
                    ($overfull | Measure-Object -Maximum).Maximum)
    } else {
        Write-Host "overfull boxes    : 0"
    }
    Write-Host "bibliography      : $((Get-Content "$doc.bbl" | Select-String '\\bibitem').Count) entries"
    Write-Host ((Get-Content "$doc.log" | Select-String 'Output written').ToString().Trim())

    # Leave only the PDF and the sources behind.
    Remove-Item "$doc.aux", "$doc.blg", "$doc.out", "$doc.spl" -ErrorAction SilentlyContinue

    if ($errors -gt 0 -or $undefined -gt 0) { $failed = $true }
}

if ($failed) { exit 1 }
