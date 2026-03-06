$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSEdition -eq "Core") {
    $powershellExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path -LiteralPath $powershellExe)) {
        throw "Windows PowerShell not found at $powershellExe"
    }

    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$script:PackageDir = "C:\Users\loofi\AppData\Local\Microsoft\WinGet\Packages\LibreHardwareMonitor.LibreHardwareMonitor_Microsoft.Winget.Source_8wekyb3d8bbwe"
$script:LibPath = Join-Path $script:PackageDir "LibreHardwareMonitorLib.dll"

. (Join-Path $PSScriptRoot "telemetry-common.ps1")

if (-not (Test-Path -LiteralPath $script:LibPath)) {
    throw "LibreHardwareMonitorLib.dll not found at $script:LibPath"
}

Add-Type -Path $script:LibPath

$computer = New-Object LibreHardwareMonitor.Hardware.Computer
$computer.IsCpuEnabled = $true
$computer.IsGpuEnabled = $true
$computer.IsMemoryEnabled = $true
$computer.IsMotherboardEnabled = $true
$computer.IsControllerEnabled = $true
$computer.IsNetworkEnabled = $true
$computer.IsStorageEnabled = $true
$computer.IsBatteryEnabled = $true
$computer.IsPsuEnabled = $true
$computer.Open()

try {
    Get-MergedSnapshot -Computer $computer | ConvertTo-Json -Depth 16
} finally {
    $computer.Close()
}
