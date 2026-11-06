# Runs the suite several times in random order to find flaky tests.
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\flaky_check.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\flaky_check.ps1 -Runs 20
#
# A flaky test is worse than a failing one: it teaches the team to ignore red.
# This script repeats the run and stops at the first difference, printing the
# seed so the exact order can be reproduced.
#
# The comparison ignores the timing at the end of the pytest summary line
# ("... in 1.95s"): the wall time is different on every run and says nothing
# about whether the test passed.

param(
    [int]$Runs = 10
)

$ErrorActionPreference = "Continue"
$python = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No virtualenv found. Create one first (see README)." -ForegroundColor Red
    exit 1
}

$failures = 0
$outcomes = @{}
$timings = @()

for ($i = 1; $i -le $Runs; $i++) {
    $seed = Get-Random -Minimum 1 -Maximum 999999
    $output = & $python -m pytest -q --random-order --random-order-seed=$seed 2>&1
    $exitCode = $LASTEXITCODE

    # The summary is the last line that contains the pass/fail counts.
    $summary = ($output | Where-Object { $_ -match '\d+ (passed|failed|error)' } | Select-Object -Last 1)
    if (-not $summary) { $summary = ($output | Select-Object -Last 1) }

    # Key for comparison: the counts only, with the timing stripped off.
    $key = ($summary -replace '\s+in\s+[\d.]+s\s*$', '').Trim()
    $time = if ($summary -match 'in\s+([\d.]+)s') { [double]$matches[1] } else { 0 }

    if ($key) { $outcomes[$key] = 1 + ($outcomes[$key] -as [int]) }
    if ($time -gt 0) { $timings += $time }

    Write-Host ("run {0,2}/{1}  seed {2,6}  {3}" -f $i, $Runs, $seed, $summary)

    if ($exitCode -ne 0) {
        $failures++
        Write-Host "  ^ FAILED. Reproduce with:" -ForegroundColor Red
        Write-Host "    .\.venv\Scripts\python.exe -m pytest --random-order --random-order-seed=$seed" -ForegroundColor Red
        if ($output.Count -gt 1) {
            $output | Select-Object -Last 15 | ForEach-Object { Write-Host "    $_" }
        }
        break
    }
}

Write-Host ""
Write-Host "Distinct outcomes:"
$outcomes.GetEnumerator() | Sort-Object Name | ForEach-Object {
    Write-Host ("  {0,3} x  {1}" -f $_.Value, $_.Name)
}

if ($timings.Count -gt 0) {
    $avg = [math]::Round(($timings | Measure-Object -Average).Average, 2)
    $min = ($timings | Measure-Object -Minimum).Minimum
    $max = ($timings | Measure-Object -Maximum).Maximum
    Write-Host ("Timing: avg {0}s, min {1}s, max {2}s" -f $avg, $min, $max)
}

Write-Host ""
if ($failures -eq 0 -and $outcomes.Keys.Count -eq 1) {
    Write-Host "No flakiness in $Runs runs with random order." -ForegroundColor Green
} elseif ($failures -eq 0) {
    Write-Host "No failures, but the outcome differed between runs. Investigate:" -ForegroundColor Yellow
    $outcomes.Keys | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "Flaky behaviour found in run $i of $Runs." -ForegroundColor Red
}

