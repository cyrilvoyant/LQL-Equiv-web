# Build the manuscript. Requires MiKTeX (winget install MiKTeX.MiKTeX).
#
#   pwsh paper/build.ps1
#
# Four passes: the first writes the .aux, BibTeX resolves the citations from it,
# and the last two settle the cross-references and the reference numbers.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command pdflatex -ErrorAction SilentlyContinue)) {
    throw "pdflatex not found. Install MiKTeX: winget install MiKTeX.MiKTeX"
}

Write-Host "regenerating figures and the numbers quoted in the text..."
python figures.py | Tee-Object -FilePath figures.log

Write-Host "pass 1 of 4..."; & pdflatex -interaction=nonstopmode main.tex | Out-Null
Write-Host "bibtex...";      & bibtex main | Out-Null
Write-Host "pass 3 of 4..."; & pdflatex -interaction=nonstopmode main.tex | Out-Null
Write-Host "pass 4 of 4..."; & pdflatex -interaction=nonstopmode main.tex | Out-Null

$log = Get-Content main.log -Raw
$errors = ([regex]::Matches($log, '(?m)^! ')).Count
$undefined = ([regex]::Matches($log, '(Citation|Reference) .* undefined')).Count
$overfull = [regex]::Matches($log, 'Overfull \\hbox \(([\d.]+)pt') |
            ForEach-Object { [double]$_.Groups[1].Value }

Write-Host ""
Write-Host "errors            : $errors"
Write-Host "undefined refs    : $undefined"
if ($overfull) {
    Write-Host ("overfull boxes    : {0} (worst {1:N1} pt)" -f $overfull.Count,
                ($overfull | Measure-Object -Maximum).Maximum)
} else {
    Write-Host "overfull boxes    : 0"
}
Write-Host "bibliography      : $((Get-Content main.bbl | Select-String '\\bibitem').Count) entries"
Write-Host ((Get-Content main.log | Select-String 'Output written').ToString().Trim())

# Leave only the PDF and the sources behind.
Remove-Item main.aux, main.blg, main.out, main.spl -ErrorAction SilentlyContinue

if ($errors -gt 0 -or $undefined -gt 0) { exit 1 }
