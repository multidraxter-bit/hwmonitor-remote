.pragma library

function normalizeText(value) {
    if (value === null || typeof value === "undefined")
        return ""
    return String(value).toLowerCase()
}

function formatValue(value, unit) {
    if (value === null || typeof value === "undefined" || value === "")
        return ""

    if (Math.abs(value - Math.round(value)) < 0.01)
        value = Math.round(value)
    else
        value = Math.round(value * 10) / 10

    return unit ? value + " " + unit : String(value)
}

function classifyRow(item) {
    if (!item || item.kind !== "sensor")
        return "other"

    switch (item.type) {
    case "Temperature":
        return "temperature"
    case "Load":
        return "load"
    case "Fan":
    case "Control":
        return "cooling"
    case "Power":
    case "Voltage":
    case "Current":
        return "power"
    case "Clock":
    case "Frequency":
        return "clock"
    case "Data":
    case "SmallData":
    case "Throughput":
        return "storage"
    default:
        return "other"
    }
}

function rowSeverity(item, thresholds) {
    if (!item || item.kind !== "sensor" || item.value === null || typeof item.value === "undefined")
        return "normal"

    var warnTemp = thresholds && thresholds.warnTempC ? thresholds.warnTempC : 75
    var criticalTemp = thresholds && thresholds.criticalTempC ? thresholds.criticalTempC : 90
    var warnLoad = thresholds && thresholds.warnLoadPct ? thresholds.warnLoadPct : 80
    var criticalLoad = thresholds && thresholds.criticalLoadPct ? thresholds.criticalLoadPct : 95

    if (item.type === "Temperature") {
        if (item.value >= criticalTemp)
            return "critical"
        if (item.value >= warnTemp)
            return "warn"
        return "cool"
    }

    if (item.type === "Load" || item.type === "Control") {
        if (item.value >= criticalLoad)
            return "critical"
        if (item.value >= warnLoad)
            return "warn"
        return "cool"
    }

    if (item.type === "Power") {
        if (item.value >= 300)
            return "critical"
        if (item.value >= 220)
            return "warn"
    }

    return "normal"
}

function shouldExpandByDefault(item, depth) {
    if (!item)
        return false
    if (depth <= 1)
        return true
    if (item.kind === "group" && (item.name === "Temperatures" || item.name === "Fans" || item.name === "Loads"))
        return true
    return false
}

function buildRows(snapshot, expandedPaths, searchText, category, thresholds) {
    var rows = []
    var query = normalizeText(searchText)

    function walk(item, depth, path, visible) {
        if (!item)
            return

        var currentPath = path
        if (item.kind !== "machine")
            currentPath = path ? (path + "/" + item.name) : item.name

        var isSensor = item.kind === "sensor"
        var categoryName = isSensor ? classifyRow(item) : ""
        var severity = isSensor ? rowSeverity(item, thresholds) : "normal"
        var searchBlob = normalizeText((item.name || "") + " " + currentPath + " " + (item.type || ""))
        var matchesQuery = !query || searchBlob.indexOf(query) !== -1
        var hasChildren = !!(item.children && item.children.length)
        var expanded = !!expandedPaths[currentPath]
        if (hasChildren && !expanded && shouldExpandByDefault(item, depth) && !query && category === "all")
            expanded = true

        var descendantMatched = false
        if (hasChildren) {
            for (var i = 0; i < item.children.length; i++) {
                var child = item.children[i]
                var childBlob = normalizeText((child.name || "") + " " + currentPath + "/" + (child.name || "") + " " + (child.type || ""))
                if (!query || childBlob.indexOf(query) !== -1) {
                    descendantMatched = true
                    break
                }
            }
        }

        var matchesCategory = !isSensor || category === "all" || categoryName === category
        var includeRow = item.kind !== "machine" && matchesCategory && (matchesQuery || descendantMatched || !query)

        if (includeRow) {
            rows.push({
                kind: item.kind || "sensor",
                indent: depth,
                name: item.name || "Unknown",
                path: currentPath,
                value: isSensor ? formatValue(item.value, item.unit) : "",
                min: isSensor ? formatValue(item.min, item.unit) : "",
                max: isSensor ? formatValue(item.max, item.unit) : "",
                rawValue: item.value,
                rawMin: item.min,
                rawMax: item.max,
                sensorType: item.type || "",
                category: categoryName,
                severity: severity,
                hasChildren: hasChildren,
                expanded: expanded
            })
        }

        if (!hasChildren)
            return

        var childVisible = visible && (expanded || !!query)
        if (!childVisible)
            return

        for (var c = 0; c < item.children.length; c++)
            walk(item.children[c], item.kind === "machine" ? depth : depth + 1, currentPath, childVisible)
    }

    walk(snapshot, 0, "", true)
    return rows
}

function scoreText(name, hints) {
    var score = 0
    for (var i = 0; i < hints.length; i++) {
        if (name.indexOf(hints[i]) !== -1)
            score += 10
    }
    return score
}

function findBestSensor(node, options) {
    var best = null
    var matchHardware = options.hardwareHints || []
    var matchSensors = options.sensorHints || []
    var sensorType = options.sensorType || ""

    function visit(item, score) {
        if (!item)
            return

        var nextScore = score
        if (item.kind === "hardware" && item.name)
            nextScore += scoreText(item.name, matchHardware)

        if (item.kind === "sensor" && item.value !== null) {
            var sensorScore = nextScore
            if (!sensorType || item.type === sensorType)
                sensorScore += 5
            if (item.name)
                sensorScore += scoreText(item.name, matchSensors)
            if (sensorType && item.type !== sensorType)
                sensorScore -= 20

            if (best === null || sensorScore > best.score) {
                best = {
                    score: sensorScore,
                    name: item.name || "",
                    value: formatValue(item.value, item.unit),
                    rawValue: item.value,
                    unit: item.unit || "",
                    type: item.type || ""
                }
            }
        }

        var children = item.children || []
        for (var i = 0; i < children.length; i++)
            visit(children[i], nextScore)
    }

    visit(node, 0)
    return best
}

function summarizeNode(snapshot, thresholds) {
    if (!snapshot || !snapshot.children)
        return []

    var cpuTemp = findBestSensor(snapshot, {
        hardwareHints: ["Intel", "AMD", "Ryzen", "Core", "CPU"],
        sensorHints: ["Package", "CPU Package", "Core (Tctl/Tdie)", "Core Max"],
        sensorType: "Temperature"
    })
    var cpuCoreHot = findBestSensor(snapshot, {
        hardwareHints: ["Intel", "AMD", "Ryzen", "Core", "CPU"],
        sensorHints: ["Core Max", "P-core", "Core"],
        sensorType: "Temperature"
    })
    var cpuLoad = findBestSensor(snapshot, {
        hardwareHints: ["Intel", "AMD", "Ryzen", "Core", "CPU"],
        sensorHints: ["Total", "CPU Total"],
        sensorType: "Load"
    })
    var gpuTemp = findBestSensor(snapshot, {
        hardwareHints: ["NVIDIA", "Radeon", "Arc", "GPU"],
        sensorHints: ["Hot Spot", "GPU Core", "Core"],
        sensorType: "Temperature"
    })
    var gpuLoad = findBestSensor(snapshot, {
        hardwareHints: ["NVIDIA", "Radeon", "Arc", "GPU"],
        sensorHints: ["GPU Core", "D3D 3D", "Core"],
        sensorType: "Load"
    })
    var gpuPower = findBestSensor(snapshot, {
        hardwareHints: ["NVIDIA", "Radeon", "Arc", "GPU"],
        sensorHints: ["Board Power", "GPU Power", "Total Board"],
        sensorType: "Power"
    })
    var fan = findBestSensor(snapshot, {
        hardwareHints: ["ASUS", "MSI", "Gigabyte", "Board", "Motherboard"],
        sensorHints: ["CPU", "Chassis", "System", "Fan"],
        sensorType: "Fan"
    })
    var drive = findBestSensor(snapshot, {
        hardwareHints: ["SSD", "NVMe", "Samsung", "WD", "Kingston", "Crucial"],
        sensorHints: ["Temperature", "Assembly"],
        sensorType: "Temperature"
    })

    return [
        {
            title: "CPU",
            primary: cpuTemp ? cpuTemp.value : "--",
            secondary: cpuLoad ? cpuLoad.value : "No load sensor",
            tertiary: cpuCoreHot ? cpuCoreHot.name + " " + cpuCoreHot.value : "No core max",
            rawPrimary: cpuTemp ? cpuTemp.rawValue : null,
            severity: cpuTemp ? rowSeverity({ kind: "sensor", type: "Temperature", value: cpuTemp.rawValue }, thresholds) : "normal"
        },
        {
            title: "GPU",
            primary: gpuTemp ? gpuTemp.value : "--",
            secondary: gpuLoad ? gpuLoad.value : "No load sensor",
            tertiary: gpuPower ? gpuPower.value : "No power sensor",
            rawPrimary: gpuTemp ? gpuTemp.rawValue : null,
            severity: gpuTemp ? rowSeverity({ kind: "sensor", type: "Temperature", value: gpuTemp.rawValue }, thresholds) : "normal"
        },
        {
            title: "Cooling",
            primary: fan ? fan.value : "--",
            secondary: fan ? fan.name : "No fan sensor",
            tertiary: cpuCoreHot ? "Peak " + cpuCoreHot.value : "",
            rawPrimary: fan ? fan.rawValue : null,
            severity: "normal"
        },
        {
            title: "Drive",
            primary: drive ? drive.value : "--",
            secondary: drive ? drive.name : "No drive temp",
            tertiary: "",
            rawPrimary: drive ? drive.rawValue : null,
            severity: drive ? rowSeverity({ kind: "sensor", type: "Temperature", value: drive.rawValue }, thresholds) : "normal"
        }
    ]
}

function countSensors(rows) {
    var counts = {
        total: 0,
        temperature: 0,
        load: 0,
        cooling: 0,
        power: 0,
        clock: 0,
        storage: 0,
        other: 0
    }

    for (var i = 0; i < rows.length; i++) {
        if (rows[i].kind !== "sensor")
            continue
        counts.total += 1
        counts[rows[i].category] += 1
    }

    return counts
}

function overallSeverity(summaryCards) {
    var level = "normal"
    for (var i = 0; i < summaryCards.length; i++) {
        var severity = summaryCards[i].severity
        if (severity === "critical")
            return "critical"
        if (severity === "warn")
            level = "warn"
    }
    return level
}

function collectAlertSensors(rows) {
    var alerts = []
    for (var i = 0; i < rows.length; i++) {
        var row = rows[i]
        if (row.kind === "sensor" && (row.severity === "warn" || row.severity === "critical"))
            alerts.push(row)
    }
    alerts.sort(function(a, b) {
        if (a.severity === b.severity)
            return (b.rawValue || 0) - (a.rawValue || 0)
        return a.severity === "critical" ? -1 : 1
    })
    return alerts
}

function collectFocusSensors(rows) {
    var picks = []
    var desired = [
        { label: "CPU Package", match: ["Package", "CPU Package"], type: "Temperature" },
        { label: "CPU Load", match: ["Total", "CPU Total"], type: "Load" },
        { label: "GPU Hotspot", match: ["Hot Spot", "Hotspot"], type: "Temperature" },
        { label: "GPU Load", match: ["GPU Core", "D3D 3D", "Core"], type: "Load" },
        { label: "GPU Power", match: ["Board Power", "GPU Power", "Total Board"], type: "Power" },
        { label: "CPU Fan", match: ["CPU", "Fan"], type: "Fan" },
        { label: "Drive Temp", match: ["Temperature", "Assembly"], type: "Temperature" }
    ]

    for (var d = 0; d < desired.length; d++) {
        var best = null
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (row.kind !== "sensor")
                continue
            if (desired[d].type && row.sensorType !== desired[d].type)
                continue

            var score = 0
            for (var h = 0; h < desired[d].match.length; h++) {
                if (row.name.indexOf(desired[d].match[h]) !== -1 || row.path.indexOf(desired[d].match[h]) !== -1)
                    score += 10
            }
            if (score === 0)
                continue

            if (!best || score > best.score) {
                best = {
                    score: score,
                    label: desired[d].label,
                    value: row.value,
                    path: row.path,
                    severity: row.severity
                }
            }
        }
        if (best)
            picks.push(best)
    }

    return picks.slice(0, 6)
}

function collectFavoriteRows(rows) {
    var favorites = []
    var seen = {}
    var priority = [
        ["CPU Package", "Package"],
        ["CPU Load", "CPU Total"],
        ["GPU Hotspot", "Hot Spot"],
        ["GPU Load", "GPU Core"],
        ["GPU Power", "Board Power"],
        ["CPU Fan", "CPU"],
        ["Drive Temp", "Temperature"]
    ]

    for (var p = 0; p < priority.length; p++) {
        var label = priority[p][0]
        var hint = priority[p][1]
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (row.kind !== "sensor")
                continue
            if (seen[row.path])
                continue
            if (row.name.indexOf(hint) === -1 && row.path.indexOf(hint) === -1)
                continue
            favorites.push({
                label: label,
                name: row.name,
                value: row.value,
                min: row.min,
                max: row.max,
                severity: row.severity,
                path: row.path
            })
            seen[row.path] = true
            break
        }
    }

    return favorites.slice(0, 8)
}

function collectCpuCoreRows(rows) {
    var out = []
    for (var i = 0; i < rows.length; i++) {
        var row = rows[i]
        if (row.kind !== "sensor")
            continue
        if (row.sensorType !== "Temperature")
            continue
        if (row.name.indexOf("Core") === -1 && row.name.indexOf("P-core") === -1 && row.name.indexOf("E-core") === -1)
            continue
        if (row.path.indexOf("Intel") === -1 && row.path.indexOf("AMD") === -1 && row.path.indexOf("Ryzen") === -1 && row.path.indexOf("Core") === -1)
            continue
        out.push({
            name: row.name,
            value: row.value,
            rawValue: row.rawValue,
            severity: row.severity
        })
    }

    out.sort(function(a, b) { return (b.rawValue || 0) - (a.rawValue || 0) })
    return out.slice(0, 12)
}
