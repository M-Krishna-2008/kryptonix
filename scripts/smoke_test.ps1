# ==============================================================================
# Automated End-to-End Smoke Test Script
# Verifies Gateway Health, Reverse-Proxying, and Submits Sample Evidence to all 4 Modules
# ==============================================================================

[CmdletBinding()]
param(
    [string]$GatewayUrl = "http://127.0.0.1:8080"
)

$ErrorActionPreference = "Stop"
$RootPath = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   AI Forensics Platform - Automated Smoke Test" -ForegroundColor Cyan
Write-Host "   Target Gateway: $GatewayUrl" -ForegroundColor DarkGray
Write-Host "======================================================================" -ForegroundColor Cyan

$TotalTests = 0
$PassedTests = 0

function Assert-Test {
    param([string]$Name, [scriptblock]$Action)
    $script:TotalTests++
    Write-Host -NoNewline ("Testing: {0,-50} ... " -f $Name)
    try {
        & $Action
        Write-Host "[PASS]" -ForegroundColor Green
        $script:PassedTests++
    } catch {
        Write-Host "[FAIL]" -ForegroundColor Red
        Write-Host "   Error: $_" -ForegroundColor DarkRed
    }
}

# 1. Gateway Health Check
Assert-Test "Gateway /api/health Aggregator" {
    $resp = Invoke-RestMethod -Uri "$GatewayUrl/api/health" -TimeoutSec 10
    if ($resp.status -notin @("healthy", "degraded")) {
        throw "Unexpected status: $($resp.status)"
    }
}

# 2. Gateway Config Endpoint
Assert-Test "Gateway /api/config Manifest Delivery" {
    $resp = Invoke-RestMethod -Uri "$GatewayUrl/api/config" -TimeoutSec 5
    if (-not $resp.modules -or $resp.modules.Count -lt 4) {
        throw "Expected at least 4 modules in config, got $($resp.modules.Count)"
    }
}

# Helper to submit file via multipart form
function Submit-ForensicFile {
    param(
        [string]$ModuleId,
        [string]$FilePath
    )
    $uri = "$GatewayUrl/api/jobs"
    $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
    $fileName = [System.IO.Path]::GetFileName($FilePath)

    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    
    $bodyLines = @(
        "--$boundary",
        "Content-Disposition: form-data; name=`"module_id`"",
        "",
        "$ModuleId",
        "--$boundary",
        "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`"",
        "Content-Type: application/octet-stream",
        ""
    )
    $headerBytes = [System.Text.Encoding]::ASCII.GetBytes(($bodyLines -join $LF) + $LF)
    $footerBytes = [System.Text.Encoding]::ASCII.GetBytes("$LF--$boundary--$LF")

    $combined = [byte[]]::new($headerBytes.Length + $fileBytes.Length + $footerBytes.Length)
    [System.Buffer]::BlockCopy($headerBytes, 0, $combined, 0, $headerBytes.Length)
    [System.Buffer]::BlockCopy($fileBytes, 0, $combined, $headerBytes.Length, $fileBytes.Length)
    [System.Buffer]::BlockCopy($footerBytes, 0, $combined, $headerBytes.Length + $fileBytes.Length, $footerBytes.Length)

    $initResp = Invoke-RestMethod -Uri $uri -Method Post -Body $combined -ContentType "multipart/form-data; boundary=$boundary" -TimeoutSec 30
    $jobId = $initResp.job_id
    if (-not $jobId) { throw "No job_id returned" }

    # Poll until completed
    $timeout = [DateTime]::Now.AddSeconds(120)
    while ([DateTime]::Now -lt $timeout) {
        Start-Sleep -Seconds 1
        $statusResp = Invoke-RestMethod -Uri "$GatewayUrl/api/jobs/$jobId" -TimeoutSec 10
        if ($statusResp.status -eq "completed") {
            return $statusResp.result
        } elseif ($statusResp.status -eq "failed") {
            throw "Job failed: $($statusResp.error)"
        }
    }
    throw "Timed out waiting for job completion."
}

# 3. Audio Module End-to-End Test
$audioSample = Join-Path $RootPath "ai_aud\audio_forensics\tests\samples\real\sample_voice_real.wav"
if (-not (Test-Path -LiteralPath $audioSample)) {
    $audioSample = Join-Path $RootPath "ai_aud\data_audio\bonafide\genuine_1.flac"
}
if (Test-Path -LiteralPath $audioSample) {
    Assert-Test "Module [ai_aud] Audio Forensics Analysis" {
        $res = Submit-ForensicFile -ModuleId "ai_aud" -FilePath $audioSample
        if (-not $res.verdict) { throw "Missing verdict in response" }
        if (-not $res.raw_metrics.raw_metric_name -eq "bona_fide_logit") { throw "raw_metric_name is not bona_fide_logit" }
    }
}

# 4. AI Image Module End-to-End Test
$imgSample = Join-Path $RootPath "ai_img\ai_image_detection\tests\samples\sample_camera_authentic.jpg"
if (Test-Path -LiteralPath $imgSample) {
    Assert-Test "Module [ai_img] AI Image Synthesis Detection" {
        $res = Submit-ForensicFile -ModuleId "ai_img" -FilePath $imgSample
        if (-not $res.verdict) { throw "Missing verdict in response" }
        if ($res.raw_metrics.calibrated_probability -eq $null) { throw "Missing calibrated_probability" }
    }
}

# 5. Forgery Module End-to-End Test
$forgerySample = Join-Path $RootPath "image_forgery\image_forgery\tests\samples\spliced.jpg"
if (Test-Path -LiteralPath $forgerySample) {
    Assert-Test "Module [image_forgery] TruFor Tamper Localization" {
        $res = Submit-ForensicFile -ModuleId "image_forgery" -FilePath $forgerySample
        if (-not $res.verdict) { throw "Missing verdict in response" }
        if (-not $res.raw_metrics.engines.trufor) { throw "Missing TruFor engine output" }
    }
}

# 6. CCTV Module End-to-End Test
$cctvSample = Join-Path $RootPath "ai_cctv\tests\api_test_clip.mp4"
if (Test-Path -LiteralPath $cctvSample) {
    Assert-Test "Module [ai_cctv] Video Timeline & Quality Gate" {
        $res = Submit-ForensicFile -ModuleId "ai_cctv" -FilePath $cctvSample
        if (-not $res.verdict) { throw "Missing verdict in response" }
        if ($res.raw_metrics.median_p -eq $null) { throw "Missing median_p" }
        if (-not $res.raw_metrics.frame_scores) { throw "Missing frame_scores timeline" }
    }
}

# 7. Corrupt File Handling (Magic-Byte Protection)
Assert-Test "Gateway Content Signature & Magic-Byte Validation" {
    $badBytes = [System.Text.Encoding]::ASCII.GetBytes("This is plain text pretending to be an audio file.")
    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    $bodyLines = @(
        "--$boundary",
        "Content-Disposition: form-data; name=`"module_id`"",
        "",
        "ai_aud",
        "--$boundary",
        "Content-Disposition: form-data; name=`"file`"; filename=`"fake.wav`"",
        "Content-Type: audio/wav",
        ""
    )
    $headerBytes = [System.Text.Encoding]::ASCII.GetBytes(($bodyLines -join $LF) + $LF)
    $footerBytes = [System.Text.Encoding]::ASCII.GetBytes("$LF--$boundary--$LF")

    $combined = [byte[]]::new($headerBytes.Length + $badBytes.Length + $footerBytes.Length)
    [System.Buffer]::BlockCopy($headerBytes, 0, $combined, 0, $headerBytes.Length)
    [System.Buffer]::BlockCopy($badBytes, 0, $combined, $headerBytes.Length, $badBytes.Length)
    [System.Buffer]::BlockCopy($footerBytes, 0, $combined, $headerBytes.Length + $badBytes.Length, $footerBytes.Length)

    try {
        Invoke-RestMethod -Uri "$GatewayUrl/api/jobs" -Method Post -Body $combined -ContentType "multipart/form-data; boundary=$boundary" -TimeoutSec 10
        throw "Gateway should have rejected fake audio file with HTTP 400!"
    } catch {
        # Successfully caught error
        if ($_.Exception.Response.StatusCode.value__ -eq 400) {
            # Expected 400
        } else {
            throw $_
        }
    }
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   Smoke Test Results: $PassedTests / $TotalTests tests passed." -ForegroundColor $(if ($PassedTests -eq $TotalTests) { "Green" } else { "Yellow" })
Write-Host "======================================================================" -ForegroundColor Cyan
