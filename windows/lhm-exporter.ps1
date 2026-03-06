$ErrorActionPreference = "Stop"

$script:Port = 8086
$script:Prefix = "http://+:$($script:Port)/"
$script:RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:PackageDir = "C:\Users\loofi\AppData\Local\Microsoft\WinGet\Packages\LibreHardwareMonitor.LibreHardwareMonitor_Microsoft.Winget.Source_8wekyb3d8bbwe"
$script:LibPath = Join-Path $script:PackageDir "LibreHardwareMonitorLib.dll"
$script:LogPath = Join-Path $script:RootDir "lhm-exporter.log"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $script:LogPath -Value "[$timestamp] $Message"
}

function Get-DisplayName {
    param([string]$SensorType)

    switch ($SensorType) {
        "Clock" { "Clocks" }
        "Control" { "Controls" }
        "Current" { "Currents" }
        "Data" { "Data" }
        "Factor" { "Factors" }
        "Fan" { "Fans" }
        "Flow" { "Flows" }
        "Frequency" { "Frequencies" }
        "Humidity" { "Humidity" }
        "Level" { "Levels" }
        "LiquidLevel" { "Liquid Levels" }
        "Load" { "Loads" }
        "Power" { "Powers" }
        "Pressure" { "Pressures" }
        "SmallData" { "Small Data" }
        "Temperature" { "Temperatures" }
        "Throughput" { "Throughput" }
        "TimeSpan" { "Time" }
        "Voltage" { "Voltages" }
        default { "$SensorType" }
    }
}

function Get-Unit {
    param([string]$SensorType)

    switch ($SensorType) {
        "Clock" { "MHz" }
        "Control" { "%" }
        "Current" { "A" }
        "Data" { "GB" }
        "Fan" { "RPM" }
        "Flow" { "L/h" }
        "Frequency" { "Hz" }
        "Humidity" { "%" }
        "Level" { "%" }
        "LiquidLevel" { "%" }
        "Load" { "%" }
        "Power" { "W" }
        "Pressure" { "bar" }
        "SmallData" { "MB" }
        "Temperature" { "C" }
        "Throughput" { "B/s" }
        "TimeSpan" { "s" }
        "Voltage" { "V" }
        default { "" }
    }
}

function Format-Number {
    param([Nullable[float]]$Value)

    if ($null -eq $Value) {
        return $null
    }

    return [Math]::Round([double]$Value, 2)
}

function Update-HardwareNode {
    param([object]$Hardware)

    $Hardware.Update()
    foreach ($subHardware in $Hardware.SubHardware) {
        Update-HardwareNode $subHardware
    }
}

function Convert-Sensor {
    param([object]$Sensor)

    return [ordered]@{
        kind = "sensor"
        name = $Sensor.Name
        type = [string]$Sensor.SensorType
        id = [string]$Sensor.Identifier
        value = Format-Number $Sensor.Value
        min = Format-Number $Sensor.Min
        max = Format-Number $Sensor.Max
        unit = Get-Unit ([string]$Sensor.SensorType)
    }
}

function Convert-SensorGroup {
    param(
        [string]$Name,
        [object[]]$Sensors
    )

    return [ordered]@{
        kind = "group"
        name = $Name
        children = @($Sensors | Sort-Object Name | ForEach-Object { Convert-Sensor $_ })
    }
}

function Convert-Hardware {
    param([object]$Hardware)

    Update-HardwareNode $Hardware

    $groups = @()
    $groupedSensors = $Hardware.Sensors | Group-Object { [string]$_.SensorType } | Sort-Object Name
    foreach ($group in $groupedSensors) {
        $groups += Convert-SensorGroup (Get-DisplayName $group.Name) $group.Group
    }

    $subNodes = @($Hardware.SubHardware | Sort-Object Name | ForEach-Object { Convert-Hardware $_ })
    $children = @($groups + $subNodes)

    return [ordered]@{
        kind = "hardware"
        name = $Hardware.Name
        type = [string]$Hardware.HardwareType
        id = [string]$Hardware.Identifier
        children = $children
    }
}

function Get-Snapshot {
    $hardwareNodes = @($script:Computer.Hardware | Sort-Object Name | ForEach-Object { Convert-Hardware $_ })

    return [ordered]@{
        kind = "machine"
        name = $env:COMPUTERNAME
        source = "LibreHardwareMonitorLib"
        generatedAt = (Get-Date).ToString("o")
        children = $hardwareNodes
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
$listener.Start()

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
                    $payload = Get-Snapshot | ConvertTo-Json -Depth 16
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
