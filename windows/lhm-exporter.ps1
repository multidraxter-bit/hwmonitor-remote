$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSEdition -eq "Core") {
    $powershellExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path -LiteralPath $powershellExe)) {
        throw "Windows PowerShell not found at $powershellExe"
    }

    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$script:Port = 8086
$script:Prefix = "http://+:$($script:Port)/"
$script:RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:PackageDir = "C:\Users\loofi\AppData\Local\Microsoft\WinGet\Packages\LibreHardwareMonitor.LibreHardwareMonitor_Microsoft.Winget.Source_8wekyb3d8bbwe"
$script:LibPath = Join-Path $script:PackageDir "LibreHardwareMonitorLib.dll"
$script:LogPath = Join-Path $script:RootDir "lhm-exporter.log"

. (Join-Path $PSScriptRoot "telemetry-common.ps1")

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $script:LogPath -Value "[$timestamp] $Message"
}

function Test-HealthyExporter {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($script:Port)/health" -TimeoutSec 2
        return $response.StatusCode -eq 200 -and $response.Content -match '"status"\s*:\s*"ok"'
    } catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $script:LibPath)) {
    throw "LibreHardwareMonitorLib.dll not found at $script:LibPath"
}

Add-Type -Path $script:LibPath

$script:Computer = New-Object LibreHardwareMonitor.Hardware.Computer
$script:Computer.IsCpuEnabled = $true
$script:Computer.IsGpuEnabled = $true
$script:Computer.IsMemoryEnabled = $true
$script:Computer.IsMotherboardEnabled = $true
$script:Computer.IsControllerEnabled = $true
$script:Computer.IsNetworkEnabled = $true
$script:Computer.IsStorageEnabled = $true
$script:Computer.IsBatteryEnabled = $true
$script:Computer.IsPsuEnabled = $true
$script:Computer.Open()

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add($script:Prefix)

try {
    $listener.Start()
} catch {
    if (Test-HealthyExporter) {
        Write-Log "Exporter already running on $($script:Prefix); exiting duplicate launch"
        exit 0
    }
    throw
}

Write-Log "Exporter started on $($script:Prefix)"

try {
    while ($listener.IsListening) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response

        try {
            switch ($request.Url.AbsolutePath) {
                "/" {
                    $payload = [ordered]@{
                        name = "lhm-exporter"
                        status = "ok"
                        data = "http://$($env:COMPUTERNAME):$($script:Port)/data.json"
                    } | ConvertTo-Json -Depth 4
                }
                "/health" {
                    $payload = '{"status":"ok"}'
                }
                "/data.json" {
                    $payload = Get-MergedSnapshot -Computer $script:Computer | ConvertTo-Json -Depth 16
                }
                default {
                    $response.StatusCode = 404
                    $payload = '{"error":"not_found"}'
                }
            }

            $buffer = [System.Text.Encoding]::UTF8.GetBytes($payload)
            $response.ContentType = "application/json; charset=utf-8"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        } catch {
            $response.StatusCode = 500
            $payload = (@{ error = $_.Exception.Message } | ConvertTo-Json -Depth 4)
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($payload)
            $response.ContentType = "application/json; charset=utf-8"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
            Write-Log "Request failed: $($_.Exception.Message)"
        } finally {
            $response.OutputStream.Close()
        }
    }
} finally {
    Write-Log "Exporter stopping"
    $listener.Stop()
    $script:Computer.Close()
}
