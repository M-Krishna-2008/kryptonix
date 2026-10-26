param(
    [string]$Action,
    [string]$Arg1
)

$ErrorActionPreference = "SilentlyContinue"

if ($Action -eq "get_disk_free") {
    $drive = if ($Arg1) { $Arg1.Substring(0,1) } else { "C" }
    try {
        $bytes = [System.IO.DriveInfo]::new($drive).AvailableFreeSpace
        $gb = [math]::Round($bytes / 1GB, 1)
        Write-Output "$gb"
    } catch {
        Write-Output "0"
    }
} elseif ($Action -eq "get_free_port") {
    $startPort = if ($Arg1) { [int]$Arg1 } else { 8000 }
    $found = $null
    for ($p = $startPort; $p -lt ($startPort + 100); $p++) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $p)
            $tcp.Start()
            $tcp.Stop()
            $found = $p
            break
        } catch {}
    }
    if ($found) {
        Write-Output "$found"
    } else {
        Write-Output "8000"
    }
}
