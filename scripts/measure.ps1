# Measures the suite in one process and on N workers.
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\measure.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\measure.ps1 -Workers 8
#
# Prints the wall time of each run and the speed-up. Run it on the machine you
# actually care about: the numbers depend on core count and disk speed.

param(
    [int]$Workers = 4
)

$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No virtualenv found. Create one first:" -ForegroundColor Red
    Write-Host "  py -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

function Measure-Run {
    param([string[]]$Arguments)

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $python -m pytest -q @Arguments 2>&1 | Out-Null
    $sw.Stop()
    return [math]::Round($sw.Elapsed.TotalSeconds, 2)
}

Write-Host "Cores available: $env:NUMBER_OF_PROCESSORS"
Write-Host ""

$serial = Measure-Run @()
$parallel = Measure-Run @("-n", "$Workers")

$speedUp = if ($parallel -gt 0) { [math]::Round($serial / $parallel, 2) } else { 0 }

Write-Host ("Serial          : {0,6} s" -f $serial)
Write-Host ("{0,2} workers      : {1,6} s" -f $Workers, $parallel)
Write-Host ("Speed-up        : {0,6}x" -f $speedUp)
Write-Host ""

if ($speedUp -lt 1.2) {
    Write-Host "Verdict: not worth it. Worker start-up costs more than the parallel gain." -ForegroundColor Yellow
    Write-Host "Keep -n for the moment the suite grows past a few seconds." -ForegroundColor Yellow
} else {
    Write-Host "Verdict: keep it. Add '-n auto' to addopts in pytest.ini." -ForegroundColor Green
}

