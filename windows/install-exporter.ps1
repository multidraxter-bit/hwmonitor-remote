$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $root "lhm-exporter.ps1"
$startupName = "LHM Sensor Exporter"
$port = 8086

if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Missing exporter script at $scriptPath"
}

if (-not (Get-NetFirewallRule -DisplayName $startupName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $startupName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port | Out-Null
}

$runCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
New-ItemProperty -Path $runKey -Name $startupName -Value $runCommand -PropertyType String -Force | Out-Null

$existing = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match "powershell" -and $_.CommandLine -match [regex]::Escape($scriptPath)
}

foreach ($process in $existing) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-WindowStyle", "Hidden",
    "-File", $scriptPath
)

Write-Output "Installed startup entry and started $startupName on port $port"
