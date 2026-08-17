$port = 8083
$pids = @()
netstat -ano | Select-String ":${port} " | Select-String "LISTEN" | ForEach-Object {
    $parts = $_ -split '\s+'
    $pid = $parts[-1] -as [int]
    if ($pid -gt 0) { $pids += $pid }
}
$pids = $pids | Select-Object -Unique
Write-Output ("Found PIDs on port " + $port + " : " + ($pids -join ', '))
foreach ($pid in $pids) {
    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
        Write-Output ("Killed PID " + $pid)
    } catch {
        Write-Output ("Cannot kill PID " + $pid + " : " + $_.Exception.Message)
    }
}
Start-Sleep 1
$remaining = netstat -ano | Select-String (":$port ") | Select-String "LISTEN"
if ($remaining) {
    Write-Output "Port STILL in use!"
    $remaining
} else {
    Write-Output ("Port " + $port + " is now FREE")
}
