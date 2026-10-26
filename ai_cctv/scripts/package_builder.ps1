param(
    [string]$SourceRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

$src = (Resolve-Path $SourceRoot).Path
$distDir = Join-Path $src "dist"
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir -Force | Out-Null
}

$dateStr = Get-Date -Format "yyyyMMdd"
$zipName = "ai_cctv_detection_runtime_$dateStr.zip"
$zipPath = Join-Path $distDir $zipName

Write-Host "========================================================"
Write-Host " Building Slim Runtime Transfer Package (Tier D Only)"
Write-Host " Source: $src"
Write-Host " Target: $zipPath"
Write-Host "========================================================"

$stagingDir = Join-Path $distDir "staging_runtime"
if (Test-Path $stagingDir) {
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

# Define Tier D Items to Include
$tierDDirs = @(
    "ai_cctv_detection",
    "models",
    "scripts",
    "tests",
    "tools"
)

$tierDFiles = @(
    "check_system.bat",
    "check_system.ps1",
    "run_platform.bat",
    "stop_platform.bat",
    "clean_project.bat",
    "archive_training_data.bat",
    "restore_training_data.bat",
    "verify_package.bat",
    "main_standalone.py",
    "requirements-lock.txt",
    "requirements.txt",
    "MODULE_MANIFEST.json",
    "ENVIRONMENT.md",
    "PORTABILITY_REPORT.md",
    "SETUP_ON_NEW_LAPTOP.md",
    "PACKAGE_CONTENTS.md",
    "ARCHIVED_DATA.md",
    "README.md",
    "LICENSE_NOTES.md",
    "TRAINING.md",
    "portability_test.wsb",
    ".gitignore"
)

Write-Host "`n[1/4] Staging Tier D directories..."
foreach ($d in $tierDDirs) {
    $srcDir = Join-Path $src $d
    $dstDir = Join-Path $stagingDir $d
    if (Test-Path $srcDir) {
        Write-Host "  Staging $d/..."
        # Copy while excluding any accidental __pycache__ or .pyc
        Copy-Item -Path $srcDir -Destination $dstDir -Recurse -Force
        Get-ChildItem -Path $dstDir -Recurse -Filter "__pycache__" -Directory -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Path $dstDir -Recurse -Filter "*.pyc" -File -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "`n[2/4] Staging Tier D files..."
foreach ($f in $tierDFiles) {
    $srcFile = Join-Path $src $f
    $dstFile = Join-Path $stagingDir $f
    if (Test-Path $srcFile) {
        Copy-Item -Path $srcFile -Destination $dstFile -Force
        Write-Host "  Staged $f"
    }
}

Write-Host "`n[3/4] Generating MANIFEST_SHA256.txt for package..."
$manifestLines = @()
$manifestLines += "# PS-05 Runtime Transfer Package Manifest"
$manifestLines += "# Generated on: $((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss UTC'))"
$manifestLines += ""

$allStagedFiles = Get-ChildItem -Path $stagingDir -Recurse -File | Sort-Object FullName
foreach ($sf in $allStagedFiles) {
    $rel = $sf.FullName.Substring($stagingDir.Length).TrimStart('\', '/')
    $hash = (Get-FileHash -Path $sf.FullName -Algorithm SHA256).Hash.ToLower()
    $manifestLines += "$hash  $rel"
}

$manifestOut = Join-Path $stagingDir "MANIFEST_SHA256.txt"
$manifestLines | Out-File -FilePath $manifestOut -Encoding utf8
Write-Host "  [OK] Manifest created with $($allStagedFiles.Count) verified file hashes."

Write-Host "`n[4/4] Creating ZIP archive..."
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

$tarCmd = Get-Command tar.exe -ErrorAction SilentlyContinue
if ($tarCmd) {
    Write-Host "  Compressing with tar.exe (fast zip)..."
    Push-Location $stagingDir
    try {
        & tar.exe -a -c -f $zipPath *
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  Compressing with Compress-Archive..."
    Compress-Archive -Path "$stagingDir\*" -DestinationPath $zipPath -CompressionLevel Optimal
}

# Cleanup staging
Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue

$zipSize = (Get-Item $zipPath).Length
$zipMb = [math]::Round($zipSize / 1MB, 2)

Write-Host "`n========================================================"
Write-Host " TRANSFER PACKAGE CREATED SUCCESSFULLY!" -ForegroundColor Green
Write-Host " Package File: $zipPath"
Write-Host " Package Size: $('{0:N0}' -f $zipSize) bytes ($zipMb MB)"
Write-Host "========================================================"
