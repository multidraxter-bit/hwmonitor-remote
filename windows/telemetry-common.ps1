$ErrorActionPreference = "Stop"

$script:TelemetryConfigPath = Join-Path $PSScriptRoot "telemetry-sources.json"
$script:HwInfoSharedMemoryScriptPath = Join-Path $PSScriptRoot "hwinfo_shared_memory.py"

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
        "Latency" { "Latency" }
        "Level" { "Levels" }
        "LiquidLevel" { "Liquid Levels" }
        "Load" { "Loads" }
        "Metric" { "Metrics" }
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
        "Latency" { "ms" }
        "Level" { "%" }
        "LiquidLevel" { "%" }
        "Load" { "%" }
        "Metric" { "" }
        "Power" { "W" }
        "Pressure" { "bar" }
        "SmallData" { "MB" }
        "Temperature" { "C" }
        "Throughput" { "B/s" }
        "TimeSpan" { "ms" }
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

function Get-TelemetryConfig {
    if (-not (Test-Path -LiteralPath $script:TelemetryConfigPath)) {
        return @{}
    }
    try {
        $raw = Get-Content -LiteralPath $script:TelemetryConfigPath -Raw -Encoding UTF8
        if (-not $raw.Trim()) {
            return @{}
        }
        $parsed = ConvertFrom-Json -InputObject $raw
        return ConvertTo-Hashtable $parsed
    } catch {
        throw "Unable to parse telemetry config at $script:TelemetryConfigPath: $($_.Exception.Message)"
    }
}

function ConvertTo-Hashtable {
    param([object]$InputObject)

    if ($null -eq $InputObject) {
        return $null
    }

    if (
        $InputObject -is [string] -or
        $InputObject -is [char] -or
        $InputObject -is [bool] -or
        $InputObject -is [byte] -or
        $InputObject -is [sbyte] -or
        $InputObject -is [int16] -or
        $InputObject -is [uint16] -or
        $InputObject -is [int32] -or
        $InputObject -is [uint32] -or
        $InputObject -is [int64] -or
        $InputObject -is [uint64] -or
        $InputObject -is [single] -or
        $InputObject -is [double] -or
        $InputObject -is [decimal] -or
        $InputObject -is [datetime]
    ) {
        return $InputObject
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        $out = @{}
        foreach ($key in $InputObject.Keys) {
            $out[$key] = ConvertTo-Hashtable $InputObject[$key]
        }
        return $out
    }

    if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
        $items = @()
        foreach ($item in $InputObject) {
            $items += ,(ConvertTo-Hashtable $item)
        }
        return $items
    }

    $properties = $InputObject.PSObject.Properties
    if ($properties.Count -gt 0) {
        $out = @{}
        foreach ($property in $properties) {
            $out[$property.Name] = ConvertTo-Hashtable $property.Value
        }
        return $out
    }

    return $InputObject
}

function Get-ConfigValueOrDefault {
    param(
        [object]$Config,
        [string]$Name,
        $DefaultValue
    )

    if (-not $Config) {
        return $DefaultValue
    }

    if ($Config -is [System.Collections.IDictionary]) {
        if ($Config.ContainsKey($Name) -and $null -ne $Config[$Name] -and [string]$Config[$Name] -ne "") {
            return $Config[$Name]
        }
        return $DefaultValue
    }

    $property = $Config.PSObject.Properties[$Name]
    if ($property -and $null -ne $property.Value -and [string]$property.Value -ne "") {
        return $property.Value
    }

    return $DefaultValue
}

function Get-LatestDelimitedRow {
    param(
        [string]$Path,
        [string]$Delimiter = ","
    )

    $resolvedPath = Resolve-TelemetryPath -Path $Path
    if (-not $resolvedPath) {
        return $null
    }

    $content = Get-Content -LiteralPath $resolvedPath -Encoding UTF8 | Where-Object { $_.Trim() }
    if ($content.Count -lt 2) {
        return $null
    }

    $header = $content[0]
    $lastLine = $content[-1]
    return ConvertFrom-Csv -InputObject @($header, $lastLine) -Delimiter $Delimiter | Select-Object -First 1
}

function Resolve-TelemetryPath {
    param([string]$Path)

    if (-not $Path) {
        return $null
    }

    $hasWildcard = $Path.IndexOfAny(@('*', '?')) -ge 0
    if ($hasWildcard) {
        $match = Get-ChildItem -Path $Path -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
        return $null
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        $match = Get-ChildItem -LiteralPath $item.FullName -Filter "*.csv" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
        return $null
    }

    return $item.FullName
}

function Convert-StringToNumber {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if (-not $text.Trim()) {
        return $null
    }

    if ($text -match '^(NA|N/A|nan|NaN|None|Unavailable)$') {
        return $null
    }

    $normalized = $text.Trim()
    if ($normalized -match '[-+]?\d+(?:[.,]\d+)?') {
        $number = $Matches[0]
        if ($number.Contains(",") -and -not $number.Contains(".")) {
            $number = $number.Replace(",", ".")
        } elseif ($number.Contains(",") -and $number.Contains(".")) {
            $number = $number.Replace(",", "")
        }
        try {
            return [double]::Parse($number, [System.Globalization.CultureInfo]::InvariantCulture)
        } catch {
            return $null
        }
    }

    return $null
}

function Split-MetricNameAndUnit {
    param([string]$Header)

    if ($Header -match '^(.*?)[\s]*\[(.+?)\]\s*$') {
        return @{
            Name = $Matches[1].Trim()
            Unit = $Matches[2].Trim()
        }
    }

    return @{
        Name = $Header.Trim()
        Unit = ""
    }
}

function Get-MetricType {
    param(
        [string]$Name,
        [string]$Unit
    )

    $haystack = "$Name $Unit".ToLowerInvariant()

    if ($haystack -match 'temp|hot spot|junction') { return "Temperature" }
    if ($haystack -match 'util|usage|busy|load') { return "Load" }
    if ($haystack -match 'power|watt') { return "Power" }
    if ($haystack -match 'fan|rpm') { return "Fan" }
    if ($haystack -match 'clock|freq|mhz|ghz') { return "Clock" }
    if ($haystack -match 'volt') { return "Voltage" }
    if ($haystack -match 'current|amp') { return "Current" }
    if ($haystack -match 'frame.?time|latency|render.?time|gpu.?time|cpu.?time|ms') { return "TimeSpan" }
    if ($haystack -match 'fps|frame.?rate') { return "Frequency" }
    if ($haystack -match 'bandwidth|throughput|bytes/s|mb/s|gb/s') { return "Throughput" }
    if ($haystack -match 'memory|vram|ram|frametime|mb|gb') { return "Data" }
    return "Metric"
}

function Get-MetricUnit {
    param(
        [string]$Name,
        [string]$ParsedUnit,
        [string]$SensorType
    )

    if ($ParsedUnit) {
        return $ParsedUnit
    }

    $haystack = $Name.ToLowerInvariant()
    if ($haystack -match 'fps|frame.?rate') { return "FPS" }
    if ($haystack -match 'ms|frame.?time|latency|render.?time|gpu.?time|cpu.?time') { return "ms" }
    if ($haystack -match 'bandwidth' -and $haystack -match 'mb') { return "MB/s" }
    if ($haystack -match 'bandwidth' -and $haystack -match 'gb') { return "GB/s" }
    return Get-Unit $SensorType
}

function Should-IncludeMetric {
    param(
        [string]$Name,
        [hashtable]$Config
    )

    $includeColumns = @($Config.includeColumns | Where-Object { $null -ne $_ -and [string]$_ -ne "" })
    if ($includeColumns.Count -gt 0) {
        return $includeColumns -contains $Name
    }

    $excludeColumns = @(
        "Date", "Time", "Timestamp", "Application", "ApplicationName",
        "ProcessName", "ProcessID", "PID", "SwapChainAddress", "Runtime"
    ) + @($Config.excludeColumns | Where-Object { $null -ne $_ -and [string]$_ -ne "" })
    return -not ($excludeColumns -contains $Name)
}

function Convert-FlatMetricRowToHardware {
    param(
        [string]$SourceName,
        [string]$SourceId,
        [object]$Row,
        [hashtable]$Config
    )

    $groups = @{}
    foreach ($property in $Row.PSObject.Properties) {
        $header = [string]$property.Name
        if (-not (Should-IncludeMetric -Name $header -Config $Config)) {
            continue
        }

        $parsed = Split-MetricNameAndUnit $header
        $value = Convert-StringToNumber $property.Value
        if ($null -eq $value) {
            continue
        }

        $displayName = if ($Config.renameColumns -and $Config.renameColumns.ContainsKey($header)) {
            [string]$Config.renameColumns[$header]
        } else {
            $parsed.Name
        }
        $sensorType = Get-MetricType -Name $displayName -Unit $parsed.Unit
        $unit = if ($Config.units -and $Config.units.ContainsKey($header)) {
            [string]$Config.units[$header]
        } else {
            Get-MetricUnit -Name $displayName -ParsedUnit $parsed.Unit -SensorType $sensorType
        }

        $groupName = if ($Config.groupMap -and $Config.groupMap.ContainsKey($header)) {
            [string]$Config.groupMap[$header]
        } else {
            Get-DisplayName $sensorType
        }
        if (-not $groups.ContainsKey($groupName)) {
            $groups[$groupName] = @()
        }

        $groups[$groupName] += [ordered]@{
            kind = "sensor"
            name = $displayName
            type = $sensorType
            id = "$SourceId/$header"
            value = Format-Number $value
            min = $null
            max = $null
            unit = $unit
        }
    }

    if ($groups.Count -eq 0) {
        return $null
    }

    $children = foreach ($groupName in ($groups.Keys | Sort-Object)) {
        [ordered]@{
            kind = "group"
            name = $groupName
            children = @($groups[$groupName] | Sort-Object name)
        }
    }

    return [ordered]@{
        kind = "hardware"
        name = $SourceName
        type = "ExternalTelemetry"
        id = $SourceId
        children = @($children)
    }
}

function Invoke-PythonJsonScript {
    param(
        [string]$ScriptPath,
        [string]$PythonPath = "python"
    )

    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        return $null
    }

    try {
        $candidates = @()
        if ($PythonPath) {
            $candidates += $PythonPath
        }
        $candidates += @(
            "python",
            "py",
            "C:\Program Files\PyManager\python.exe",
            "C:\Windows\py.exe"
        )

        foreach ($candidate in ($candidates | Select-Object -Unique)) {
            try {
                $output = & $candidate $ScriptPath 2>$null
                if ($LASTEXITCODE -eq 0 -and $output) {
                    return ConvertTo-Hashtable (ConvertFrom-Json -InputObject ($output -join "`n"))
                }
            } catch {
                continue
            }
        }

        return $null
    } catch {
        return $null
    }
}

function Convert-StructuredMetricsToHardware {
    param(
        [string]$SourceName,
        [string]$SourceId,
        [object[]]$Metrics,
        [hashtable]$Config
    )

    if (-not $Metrics -or $Metrics.Count -eq 0) {
        return $null
    }

    $hardwareBuckets = @{}
    foreach ($metric in $Metrics) {
        $rawName = [string](Get-ConfigValueOrDefault -Config $metric -Name "name" -DefaultValue "")
        if (-not $rawName) {
            continue
        }

        if (-not (Should-IncludeMetric -Name $rawName -Config $Config)) {
            continue
        }

        $displayName = if ($Config.renameColumns -and $Config.renameColumns.ContainsKey($rawName)) {
            [string]$Config.renameColumns[$rawName]
        } else {
            $rawName
        }

        $groupLabel = [string](Get-ConfigValueOrDefault -Config $metric -Name "group" -DefaultValue $SourceName)
        if (-not $groupLabel) {
            $groupLabel = $SourceName
        }
        if (-not $hardwareBuckets.ContainsKey($groupLabel)) {
            $hardwareBuckets[$groupLabel] = @{}
        }

        $rawUnit = [string](Get-ConfigValueOrDefault -Config $metric -Name "unit" -DefaultValue "")
        $sensorType = Get-MetricType -Name $displayName -Unit $rawUnit
        $unit = if ($Config.units -and $Config.units.ContainsKey($rawName)) {
            [string]$Config.units[$rawName]
        } else {
            Get-MetricUnit -Name $displayName -ParsedUnit $rawUnit -SensorType $sensorType
        }

        $groupName = if ($Config.groupMap -and $Config.groupMap.ContainsKey($rawName)) {
            [string]$Config.groupMap[$rawName]
        } else {
            Get-DisplayName $sensorType
        }
        if (-not $hardwareBuckets[$groupLabel].ContainsKey($groupName)) {
            $hardwareBuckets[$groupLabel][$groupName] = @()
        }

        $metricId = Get-ConfigValueOrDefault -Config $metric -Name "id" -DefaultValue $rawName
        $sensorNode = [ordered]@{
            kind = "sensor"
            name = $displayName
            type = $sensorType
            id = "$SourceId/$groupLabel/$metricId"
            value = Format-Number (Convert-StringToNumber (Get-ConfigValueOrDefault -Config $metric -Name "value" -DefaultValue $null))
            min = Format-Number (Convert-StringToNumber (Get-ConfigValueOrDefault -Config $metric -Name "min" -DefaultValue $null))
            max = Format-Number (Convert-StringToNumber (Get-ConfigValueOrDefault -Config $metric -Name "max" -DefaultValue $null))
            unit = $unit
        }

        $avgValue = Convert-StringToNumber (Get-ConfigValueOrDefault -Config $metric -Name "avg" -DefaultValue $null)
        if ($null -ne $avgValue) {
            $sensorNode.avg = Format-Number $avgValue
        }

        $hardwareBuckets[$groupLabel][$groupName] += $sensorNode
    }

    if ($hardwareBuckets.Count -eq 0) {
        return $null
    }

    $nodes = foreach ($hardwareName in ($hardwareBuckets.Keys | Sort-Object)) {
        $groupNodes = foreach ($groupName in ($hardwareBuckets[$hardwareName].Keys | Sort-Object)) {
            [ordered]@{
                kind = "group"
                name = $groupName
                children = @($hardwareBuckets[$hardwareName][$groupName] | Sort-Object name)
            }
        }

        [ordered]@{
            kind = "hardware"
            name = $hardwareName
            type = "ExternalTelemetry"
            id = "$SourceId/$hardwareName"
            children = @($groupNodes)
        }
    }

    if ($nodes.Count -eq 1) {
        return $nodes[0]
    }

    return [ordered]@{
        kind = "hardware"
        name = $SourceName
        type = "ExternalTelemetry"
        id = $SourceId
        children = @($nodes)
    }
}

function Get-HwInfoNode {
    param([hashtable]$Config)

    if (-not $Config.enabled) {
        return $null
    }

    $mode = [string](Get-ConfigValueOrDefault -Config $Config -Name "mode" -DefaultValue "")
    $preferSharedMemory = $mode -eq "shared_memory" -or $mode -eq "shared" -or [bool](Get-ConfigValueOrDefault -Config $Config -Name "sharedMemory" -DefaultValue $false)
    if ($preferSharedMemory) {
        $pythonPath = [string](Get-ConfigValueOrDefault -Config $Config -Name "pythonPath" -DefaultValue "python")
        $payload = Invoke-PythonJsonScript -ScriptPath $script:HwInfoSharedMemoryScriptPath -PythonPath $pythonPath
        if ($payload -and $payload.sensors) {
            $node = Convert-StructuredMetricsToHardware -SourceName "HWiNFO" -SourceId "external/hwinfo" -Metrics @($payload.sensors) -Config $Config
            if ($node) {
                return $node
            }
        }
    }

    if (-not $Config.logPath) {
        return $null
    }

    $row = Get-LatestDelimitedRow -Path $Config.logPath -Delimiter (Get-ConfigValueOrDefault -Config $Config -Name "delimiter" -DefaultValue ";")
    if ($null -eq $row) {
        return $null
    }

    return Convert-FlatMetricRowToHardware -SourceName "HWiNFO" -SourceId "external/hwinfo" -Row $row -Config $Config
}

function Get-PresentMonNode {
    param([hashtable]$Config)

    if (-not $Config.enabled -or -not $Config.csvPath) {
        return $null
    }

    $row = Get-LatestDelimitedRow -Path $Config.csvPath -Delimiter (Get-ConfigValueOrDefault -Config $Config -Name "delimiter" -DefaultValue ",")
    if ($null -eq $row) {
        return $null
    }

    return Convert-FlatMetricRowToHardware -SourceName "PresentMon" -SourceId "external/presentmon" -Row $row -Config $Config
}

function Get-MsiAfterburnerNode {
    param([hashtable]$Config)

    if (-not $Config.enabled -or -not $Config.logPath) {
        return $null
    }

    $row = Get-LatestDelimitedRow -Path $Config.logPath -Delimiter (Get-ConfigValueOrDefault -Config $Config -Name "delimiter" -DefaultValue ",")
    if ($null -eq $row) {
        return $null
    }

    return Convert-FlatMetricRowToHardware -SourceName "MSI Afterburner" -SourceId "external/msi-afterburner" -Row $row -Config $Config
}

function Get-OptionalTelemetryChildren {
    param([hashtable]$Config)

    $children = @()
    if ($Config.hwinfo) {
        $node = Get-HwInfoNode $Config.hwinfo
        if ($node) { $children += $node }
    }
    if ($Config.presentmon) {
        $node = Get-PresentMonNode $Config.presentmon
        if ($node) { $children += $node }
    }
    if ($Config.msiAfterburner) {
        $node = Get-MsiAfterburnerNode $Config.msiAfterburner
        if ($node) { $children += $node }
    }
    return @($children)
}

function Get-MergedSnapshot {
    param([object]$Computer)

    $hardwareNodes = @($Computer.Hardware | Sort-Object Name | ForEach-Object { Convert-Hardware $_ })
    $config = Get-TelemetryConfig
    $externalChildren = Get-OptionalTelemetryChildren $config
    $sources = @("LibreHardwareMonitorLib")
    foreach ($node in $externalChildren) {
        $sources += $node.name
    }

    return [ordered]@{
        kind = "machine"
        name = $env:COMPUTERNAME
        source = "MergedTelemetry"
        sources = @($sources)
        generatedAt = (Get-Date).ToString("o")
        children = @($hardwareNodes + $externalChildren)
    }
}
