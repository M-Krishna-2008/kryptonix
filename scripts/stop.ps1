# ==============================================================================
# Unified AI Forensics Platform Stopper
# Terminates background module daemons and gateway server cleanly
# ==============================================================================

[CmdletBinding()]
param()

$RootPath = (Resolve-Path "$PSScriptRoot\..").Path
$RuntimeDir = Join-Path $RootPath "runtime"
$PidsPath = Join-Path $RuntimeDir "pids.json"
$PortsPath = Join-Path $RuntimeDir "ports.json"

Write-Host "Stopping Unified Forensics Platform services..." -ForegroundColor Cyan

# 1. Kill tracked PIDs
if (Test-Path -LiteralPath $PidsPath) {
    try {
        $pidsData = Get-Content -LiteralPath $PidsPath -Raw | ConvertFrom-Json
        foreach ($prop in $pidsData.PSObject.Properties) {
            $serviceName = $prop.Name
            $pidToKill = $prop.Value
            if ($pidToKill) {
                $proc = Get-Process -Id $pidToKill -ErrorAction SilentlyContinue
                if ($proc) {
                    Write-Host "Stopping $serviceName (PID $pidToKill)..." -ForegroundColor Yellow
                    Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } catch {
        Write-Host "Error parsing pids.json: $_" -ForegroundColor DarkGray
    }
    Remove-Item -LiteralPath $PidsPath -Force -ErrorAction SilentlyContinue
}

# 2. Safety check: ensure ports are freed
if (Test-Path -LiteralPath $PortsPath) {
    try {
        $portsData = Get-Content -LiteralPath $PortsPath -Raw | ConvertFrom-Json
        foreach ($prop in $portsData.PSObject.Properties) {
            $port = $prop.Value
            if ($port) {
                $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
                foreach ($c in $conns) {
                    if ($c.OwningProcess -and $c.OwningProcess -ne 0) {
                        Write-Host "Freeing port $port (Killing PID $($c.OwningProcess))..." -ForegroundColor DarkGray
                        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
                    }
                }
            }
        }
    } catch {}
}

# 3. Clean runtime upload scratch files
$uploadsDir = Join-Path $RuntimeDir "uploads"
if (Test-Path -LiteralPath $uploadsDir) {
    Get-ChildItem -Path $uploadsDir -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Host "All forensic services stopped successfully." -ForegroundColor Green
