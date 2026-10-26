param(
    [string]$Action = "archive",
    [string]$SourceRoot = $PSScriptRoot,
    [string]$DestFolder = ""
)

$ErrorActionPreference = "Stop"

$src = (Resolve-Path $SourceRoot).Path
if (-not $DestFolder) {
    Write-Host "[ERROR] Destination folder argument missing." -ForegroundColor Red
    Write-Host "Usage: archive_training_data.bat <destination_folder>"
    exit 1
}

$targetDirs = @("data", "data_raw", "runs", "real", "tamp")

if ($Action -eq "archive") {
    $dst = [System.IO.Path]::GetFullPath($DestFolder)
    Write-Host "========================================================"
    Write-Host " PS-05 Training Data Archival Tool"
    Write-Host " Source:      $src"
    Write-Host " Destination: $dst"
    Write-Host "========================================================"

    if (-not (Test-Path $dst)) {
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
    }

    $manifestLines = @()
    $manifestLines += "=== PS-05 TRAINING DATA ARCHIVE MANIFEST ==="
    $manifestLines += "Created: $((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))"
    $manifestLines += "Source: $src"
    $manifestLines += "Destination: $dst"
    $manifestLines += ""

    $allSrcFiles = @()
    $totalCopiedFiles = 0
    $totalCopiedBytes = 0

    foreach ($td in $targetDirs) {
        $srcSub = Join-Path $src $td
        $dstSub = Join-Path $dst $td
        if (Test-Path $srcSub) {
            Write-Host "`n[Copying] $td/ -> $dstSub/..."
            if (-not (Test-Path $dstSub)) {
                New-Item -ItemType Directory -Path $dstSub -Force | Out-Null
            }
            # Use robocopy for fast, reliable copy on Windows
            $rc = robocopy $srcSub $dstSub /E /NFL /NDL /NP /R:2 /W:1
            
            $srcFiles = Get-ChildItem -Path $srcSub -Recurse -File
            $dstFiles = Get-ChildItem -Path $dstSub -Recurse -File
            $srcBytes = ($srcFiles | Measure-Object -Property Length -Sum).Sum
            $dstBytes = ($dstFiles | Measure-Object -Property Length -Sum).Sum

            Write-Host "  Source:      $($srcFiles.Count) files, $('{0:N0}' -f $srcBytes) bytes"
            Write-Host "  Destination: $($dstFiles.Count) files, $('{0:N0}' -f $dstBytes) bytes"

            if ($srcFiles.Count -ne $dstFiles.Count -or $srcBytes -ne $dstBytes) {
                Write-Host "  [ERROR] Mismatch in file count or byte size for $td!" -ForegroundColor Red
                exit 1
            } else {
                Write-Host "  [OK] $td copied and byte-verified successfully." -ForegroundColor Green
            }

            $totalCopiedFiles += $dstFiles.Count
            $totalCopiedBytes += $dstBytes
            $manifestLines += "Folder: $td | Files: $($dstFiles.Count) | Bytes: $dstBytes"

            foreach ($f in $srcFiles) {
                $rel = $f.FullName.Substring($src.Length).TrimStart('\', '/')
                $allSrcFiles += $rel
            }
        }
    }

    # SHA-256 Sample Verification (At least 50 random files or all files)
    Write-Host "`n[Verification] Performing SHA-256 sample check..."
    $sampleCount = [math]::Min(50, $allSrcFiles.Count)
    $sampledFiles = $allSrcFiles | Get-Random -Count $sampleCount
    if (-not ($sampledFiles -is [array])) { $sampledFiles = @($sampledFiles) }

    $manifestLines += ""
    $manifestLines += "=== VERIFIED SHA-256 SAMPLE ($($sampledFiles.Count) files) ==="

    $verifiedCount = 0
    foreach ($rel in $sampledFiles) {
        $sFile = Join-Path $src $rel
        $dFile = Join-Path $dst $rel

        $sHash = (Get-FileHash -Path $sFile -Algorithm SHA256).Hash.ToLower()
        $dHash = (Get-FileHash -Path $dFile -Algorithm SHA256).Hash.ToLower()

        if ($sHash -ne $dHash) {
            Write-Host "  [FAIL] Hash mismatch for $rel!" -ForegroundColor Red
            Write-Host "    Src: $sHash"
            Write-Host "    Dst: $dHash"
            exit 1
        }
        $manifestLines += "$sHash  $rel"
        $verifiedCount++
    }

    Write-Host "  [OK] $verifiedCount of $verifiedCount sampled files passed SHA-256 bit-level match!" -ForegroundColor Green

    $manifestPath = Join-Path $dst "ARCHIVE_MANIFEST.txt"
    $manifestLines += ""
    $manifestLines += "Total Archived Files: $totalCopiedFiles"
    $manifestLines += "Total Archived Bytes: $totalCopiedBytes ($([math]::Round($totalCopiedBytes / 1GB, 2)) GB)"
    $manifestLines += "Restore Command: restore_training_data.bat `"$dst`""
    $manifestLines | Out-File -FilePath $manifestPath -Encoding utf8

    Write-Host "`n========================================================"
    Write-Host " ARCHIVE VERIFICATION SUMMARY"
    Write-Host " Total Files Copied: $totalCopiedFiles"
    Write-Host " Total Bytes Copied: $('{0:N0}' -f $totalCopiedBytes) ($([math]::Round($totalCopiedBytes / 1GB, 2)) GB)"
    Write-Host " Manifest written:   $manifestPath"
    Write-Host " Verification:       100% MATCH (Count, Bytes, SHA-256 sample)" -ForegroundColor Green
    Write-Host "========================================================"
    exit 0
}

elseif ($Action -eq "restore") {
    $archiveDir = [System.IO.Path]::GetFullPath($DestFolder)
    Write-Host "========================================================"
    Write-Host " PS-05 Training Data Restoration Tool"
    Write-Host " Archive Source:    $archiveDir"
    Write-Host " Destination Project: $src"
    Write-Host "========================================================"

    if (-not (Test-Path $archiveDir)) {
        Write-Host "[ERROR] Archive folder not found: $archiveDir" -ForegroundColor Red
        exit 1
    }

    $manifestPath = Join-Path $archiveDir "ARCHIVE_MANIFEST.txt"
    if (Test-Path $manifestPath) {
        Write-Host "Found ARCHIVE_MANIFEST.txt at $manifestPath."
    }

    foreach ($td in $targetDirs) {
        $archSub = Join-Path $archiveDir $td
        $projSub = Join-Path $src $td
        if (Test-Path $archSub) {
            Write-Host "`n[Restoring] $td/ -> $projSub/..."
            if (-not (Test-Path $projSub)) {
                New-Item -ItemType Directory -Path $projSub -Force | Out-Null
            }
            $rc = robocopy $archSub $projSub /E /NFL /NDL /NP /R:2 /W:1

            $archFiles = Get-ChildItem -Path $archSub -Recurse -File
            $projFiles = Get-ChildItem -Path $projSub -Recurse -File
            $archBytes = ($archFiles | Measure-Object -Property Length -Sum).Sum
            $projBytes = ($projFiles | Measure-Object -Property Length -Sum).Sum

            Write-Host "  Archive: $($archFiles.Count) files, $('{0:N0}' -f $archBytes) bytes"
            Write-Host "  Project: $($projFiles.Count) files, $('{0:N0}' -f $projBytes) bytes"

            if ($archFiles.Count -ne $projFiles.Count -or $archBytes -ne $projBytes) {
                Write-Host "  [ERROR] Mismatch after restoring $td!" -ForegroundColor Red
                exit 1
            } else {
                Write-Host "  [OK] $td restored and byte-verified successfully." -ForegroundColor Green
            }
        }
    }

    Write-Host "`n========================================================"
    Write-Host " RESTORATION COMPLETED SUCCESSFULLY"
    Write-Host " Training data has been restored into $src" -ForegroundColor Green
    Write-Host "========================================================"
    exit 0
}
