$ErrorActionPreference = "Stop"

$script:PackageDir = "C:\Users\loofi\AppData\Local\Microsoft\WinGet\Packages\LibreHardwareMonitor.LibreHardwareMonitor_Microsoft.Winget.Source_8wekyb3d8bbwe"
$script:LibPath = Join-Path $script:PackageDir "LibreHardwareMonitorLib.dll"

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
    [ordered]@{
        kind = "machine"
        name = $env:COMPUTERNAME
        source = "LibreHardwareMonitorLib"
        generatedAt = (Get-Date).ToString("o")
        children = @($computer.Hardware | Sort-Object Name | ForEach-Object { Convert-Hardware $_ })
    } | ConvertTo-Json -Depth 16
} finally {
    $computer.Close()
}
