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

function rowSeverity(item) {
    if (!item || item.kind !== "sensor" || item.value === null || typeof item.value === "undefined")
        return "normal"

    if (item.type === "Temperature") {
        if (item.value >= 90)
            return "critical"
        if (item.value >= 75)
            return "warn"
        return "cool"
    }

    if (item.type === "Load" || item.type === "Control") {
        if (item.value >= 95)
            return "critical"
        if (item.value >= 80)
            return "warn"
        return "cool"
    }

    if (item.type === "Power") {
        if (item.value >= 250)
            return "warn"
    }

    return "normal"
}

function flattenTree(node) {
    var rows = []

    function walk(item, depth, path) {
        if (!item)
            return

        var nextPath = path
        if (item.kind !== "machine")
            nextPath = path + " " + (item.name || "")

        if (item.kind !== "machine") {
            rows.push({
                kind: item.kind || "sensor",
                indent: depth,
                name: item.name || "Unknown",
                path: nextPath,
                value: item.kind === "sensor" ? formatValue(item.value, item.unit) : "",
                min: item.kind === "sensor" ? formatValue(item.min, item.unit) : "",
                max: item.kind === "sensor" ? formatValue(item.max, item.unit) : "",
                rawValue: item.value,
                rawMin: item.min,
                rawMax: item.max,
                sensorType: item.type || "",
                category: classifyRow(item),
                severity: rowSeverity(item)
            })
        }

        var children = item.children || []
        for (var i = 0; i < children.length; i++)
            walk(children[i], item.kind === "machine" ? depth : depth + 1, nextPath)
    }

    walk(node, 0, "")
    return rows
}

function filterRows(rows, searchText, category) {
    var filtered = []
    var query = normalizeText(searchText)

    for (var i = 0; i < rows.length; i++) {
        var row = rows[i]
        if (category && category !== "all" && row.kind === "sensor" && row.category !== category)
            continue
        if (query && normalizeText(row.name + " " + row.path + " " + row.sensorType).indexOf(query) === -1)
            continue
        filtered.push(row)
    }

    return filtered
}

function findBestSensor(node, options) {
    var best = null
    var matchHardware = options.hardwareHints || []
    var matchSensors = options.sensorHints || []
    var sensorType = options.sensorType || ""

    function scoreText(name, hints) {
        var score = 0
        for (var i = 0; i < hints.length; i++) {
            if (name.indexOf(hints[i]) !== -1)
                score += 10
        }
        return score
    }

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

function summarizeNode(snapshot) {
    if (!snapshot || !snapshot.children)
        return []

    var cpuTemp = findBestSensor(snapshot, {
        hardwareHints: ["Intel", "AMD", "Ryzen", "Core", "CPU"],
        sensorHints: ["Package", "Core (Tctl/Tdie)", "CPU Package", "Core Max"],
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
            severity: cpuTemp ? rowSeverity({ kind: "sensor", type: "Temperature", value: cpuTemp.rawValue }) : "normal"
        },
        {
            title: "GPU",
            primary: gpuTemp ? gpuTemp.value : "--",
            secondary: gpuLoad ? gpuLoad.value : "No load sensor",
            severity: gpuTemp ? rowSeverity({ kind: "sensor", type: "Temperature", value: gpuTemp.rawValue }) : "normal"
        },
        {
            title: "Cooling",
            primary: fan ? fan.value : "--",
            secondary: fan ? fan.name : "No fan sensor",
            severity: "normal"
        },
        {
            title: "Drive",
            primary: drive ? drive.value : "--",
            secondary: drive ? drive.name : "No drive temp",
            severity: drive ? rowSeverity({ kind: "sensor", type: "Temperature", value: drive.rawValue }) : "normal"
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
