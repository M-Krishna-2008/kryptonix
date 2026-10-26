param(
    [string]$TargetDir = $PSScriptRoot
)

$ErrorActionPreference = "SilentlyContinue"
$resolvedTarget = (Resolve-Path $TargetDir).Path
$manifestPath = Join-Path $resolvedTarget "MANIFEST_SHA256.txt"

if (-not (Test-Path $manifestPath)) {
    Write-Host "[ERROR] MANIFEST_SHA256.txt not found at $manifestPath" -ForegroundColor Red
    exit 1
}

$lines = Get-Content $manifestPath | Where-Object { $_.Trim() -and -not $_.StartsWith('#') }
$total = $lines.Count
$passed = 0
$failed = 0

Write-Host "Checking $total files against manifest...`n"
foreach ($line in $lines) {
    $parts = $line.Trim() -split '\s+', 2
    if ($parts.Count -lt 2) { continue }
    $expectedHash = $parts[0].Trim().ToLower()
    $relPath = $parts[1].Trim()
    $targetFile = Join-Path $resolvedTarget $relPath

    if (-not (Test-Path $targetFile)) {
        Write-Host "  [MISSING] $relPath" -ForegroundColor Red
        $failed++
        continue
    }

    $actualHash = (Get-FileHash -Path $targetFile -Algorithm SHA256).Hash.ToLower()
    if ($actualHash -eq $expectedHash) {
        Write-Host "  [OK] $relPath" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "  [CORRUPT] $relPath" -ForegroundColor Red
        Write-Host "    Expected: $expectedHash"
        Write-Host "    Actual:   $actualHash"
        $failed++
    }
}

Write-Host "`n========================================================"
Write-Host " VERIFICATION SUMMARY: $passed Passed, $failed Failed"
if ($failed -eq 0) {
    Write-Host " STATUS: PACKAGE IS 100% INTACT AND VALID" -ForegroundColor Green
    exit 0
} else {
    Write-Host " STATUS: PACKAGE INTEGRITY FAILURE!" -ForegroundColor Red
    exit 1
}
