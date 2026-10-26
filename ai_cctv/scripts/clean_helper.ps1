param(
    [string]$TargetDir = $PSScriptRoot,
    [int]$ApplyClean = 0,
    [int]$Days = 30
)

$ErrorActionPreference = "SilentlyContinue"
$resolvedTarget = (Resolve-Path $TargetDir).Path

Write-Host "========================================================"
Write-Host " PS-05 Project Cleanup Tool (Tier A Safe Cleanup)"
Write-Host " Working Directory: $resolvedTarget"
if ($ApplyClean -eq 1) {
    Write-Host " MODE: LIVE EXECUTION (/yes specified)" -ForegroundColor Yellow
} else {
    Write-Host " MODE: DRY-RUN (No files will be deleted. Pass /yes to execute)" -ForegroundColor Cyan
}
Write-Host "========================================================"
Write-Host ""

$freedBytes = 0
$deletedCount = 0

# 1. Tier A Files
$tierAPatterns = @('*.pyc', '*.tmp', '*.tmp.mp4', 'test_bg.txt')
Write-Host "[1/4] Scanning for Tier A Junk Files..."
foreach ($pat in $tierAPatterns) {
    Get-ChildItem -Path $resolvedTarget -Filter $pat -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {
        $_.FullName -notmatch '\\\.venv\\' -and $_.FullName -notmatch '\\_backup\\'
    } | ForEach-Object {
        $sz = $_.Length
        $freedBytes += $sz
        $deletedCount++
        if ($ApplyClean -eq 1) {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
            Write-Host "  [DELETED FILE] $($_.FullName) ($sz bytes)"
        } else {
            Write-Host "  [WOULD DELETE FILE] $($_.FullName) ($sz bytes)"
        }
    }
}

# 2. Tier A Directories (__pycache__, .pytest_cache, empty weights)
Write-Host "`n[2/4] Scanning for Tier A Cache Directories..."
Get-ChildItem -Path $resolvedTarget -Recurse -Directory -Force -ErrorAction SilentlyContinue | Where-Object {
    ($_.Name -in @('__pycache__', '.pytest_cache') -or ($_.Name -eq 'weights' -and (Test-Path (Join-Path $_.FullName 'yolo26n.pt')))) -and
    $_.FullName -notmatch '\\\.venv\\' -and $_.FullName -notmatch '\\_backup\\'
} | ForEach-Object {
    $dirFiles = Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
    $dirSize = ($dirFiles | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $dirSize) { $dirSize = 0 }
    $freedBytes += $dirSize
    $deletedCount++
    if ($ApplyClean -eq 1) {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  [DELETED DIR] $($_.FullName) ($dirSize bytes)"
    } else {
        Write-Host "  [WOULD DELETE DIR] $($_.FullName) ($dirSize bytes)"
    }
}

# 3. Old artifacts, cache, and logs older than N days (default 30)
Write-Host "`n[3/4] Scanning for Tier C artifacts/cache older than $Days days..."
$cutoff = (Get-Date).AddDays(-$Days)
foreach ($sub in @('artifacts', 'cache', 'logs')) {
    $subPath = Join-Path $resolvedTarget $sub
    if (Test-Path $subPath) {
        Get-ChildItem -Path $subPath -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {
            $_.LastWriteTime -lt $cutoff -and $_.Name -ne '.gitkeep'
        } | ForEach-Object {
            $sz = $_.Length
            $freedBytes += $sz
            $deletedCount++
            if ($ApplyClean -eq 1) {
                Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                Write-Host "  [DELETED OLD] $($_.FullName) ($sz bytes)"
            } else {
                Write-Host "  [WOULD DELETE OLD] $($_.FullName) ($sz bytes)"
            }
        }
    }
}

Write-Host "`n[4/4] Summary"
$mb = [math]::Round($freedBytes / 1MB, 2)
Write-Host " Total items identified: $deletedCount"
Write-Host " Total disk space to free: $freedBytes bytes ($mb MB)"
if ($ApplyClean -ne 1) {
    Write-Host "`nPass /yes to actually perform cleanup: clean_project.bat /yes" -ForegroundColor Yellow
} else {
    Write-Host "`nCleanup completed successfully." -ForegroundColor Green
}
