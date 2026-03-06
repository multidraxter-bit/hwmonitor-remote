import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami
import org.kde.notification
import "." as Local
import "Utils.js" as Utils

PlasmoidItem {
    id: root

    readonly property bool inPanel: (Plasmoid.location === PlasmaCore.Types.TopEdge
        || Plasmoid.location === PlasmaCore.Types.RightEdge
        || Plasmoid.location === PlasmaCore.Types.BottomEdge
        || Plasmoid.location === PlasmaCore.Types.LeftEdge)

    property var snapshot: ({})
    property var allRows: []
    property var baseRows: []
    property var visibleRows: []
    property var summaryCards: []
    property var historyMap: ({})
    property var focusSensors: []
    property var cpuCoreRows: []
    property var sensorCounts: ({ total: 0, temperature: 0, load: 0, cooling: 0, power: 0, clock: 0, storage: 0, other: 0 })
    property var expandedPaths: ({})
    property string statusText: "Waiting for first refresh"
    property string sourceLabel: plasmoid.configuration.source
    property string cpuSummary: "--"
    property string gpuSummary: "--"
    property string coolingSummary: "--"
    property string driveSummary: "--"
    property string searchText: ""
    property string activeCategory: "all"
    property bool refreshOk: false
    property string lastError: ""
    property string overallLevel: "normal"
    property string lastAlertSignature: ""
    property string topAlertText: ""

    readonly property var thresholds: ({
        warnTempC: plasmoid.configuration.warnTempC,
        criticalTempC: plasmoid.configuration.criticalTempC,
        warnLoadPct: plasmoid.configuration.warnLoadPct,
        criticalLoadPct: plasmoid.configuration.criticalLoadPct
    })

    switchWidth: Kirigami.Units.gridUnit * 32
    switchHeight: Kirigami.Units.gridUnit * 34
    preferredRepresentation: inPanel ? compactRepresentation : fullRepresentation

    toolTipMainText: "HWMonitor Remote"
    toolTipSubText: statusText

    function fetchCommand() {
        var helper = "/home/loofi/hwremote-monitor/fedora/fetch_snapshot.py"
        var source = plasmoid.configuration.source.replace(/'/g, "'\\''")
        return "python3 " + helper + " --source '" + source + "'"
    }

    function refresh() {
        sourceLabel = plasmoid.configuration.source
        statusText = "Refreshing " + plasmoid.configuration.source
        executable.exec(fetchCommand(), function(cmd, out, err, code) {
            if (code !== 0) {
                refreshOk = false
                lastError = err ? err : "Refresh failed"
                statusText = "Refresh failed"
                return
            }

            try {
                var parsed = JSON.parse(out)
                if (parsed.error) {
                    refreshOk = false
                    lastError = parsed.error
                    statusText = parsed.error
                    return
                }

                snapshot = parsed
                summaryCards = Utils.summarizeNode(parsed, thresholds)
                baseRows = Utils.buildRows(parsed, expandedPaths, "", "all", thresholds)
                allRows = Utils.buildRows(parsed, expandedPaths, searchText, activeCategory, thresholds)
                focusSensors = Utils.collectFocusSensors(baseRows)
                cpuCoreRows = Utils.collectCpuCoreRows(baseRows)
                updateHistories(summaryCards)
                sensorCounts = Utils.countSensors(baseRows)
                cpuSummary = summaryCards.length > 0 ? summaryCards[0].primary : "--"
                gpuSummary = summaryCards.length > 1 ? summaryCards[1].primary : "--"
                coolingSummary = summaryCards.length > 2 ? summaryCards[2].primary : "--"
                driveSummary = summaryCards.length > 3 ? summaryCards[3].primary : "--"
                visibleRows = allRows
                overallLevel = Utils.overallSeverity(summaryCards)
                maybeNotifyAlerts()
                refreshOk = true
                lastError = ""
                statusText = "Updated " + parsed.generatedAt
            } catch (parseError) {
                refreshOk = false
                lastError = String(parseError)
                statusText = "Parse error"
            }
        })
    }

    function applyFilters() {
        visibleRows = Utils.buildRows(snapshot, expandedPaths, searchText, activeCategory, thresholds)
        allRows = visibleRows
    }

    function toggleExpanded(path) {
        expandedPaths[path] = !expandedPaths[path]
        applyFilters()
    }

    function updateHistories(cards) {
        var nextMap = {}
        for (var existingKey in historyMap)
            nextMap[existingKey] = historyMap[existingKey]
        for (var i = 0; i < cards.length; i++) {
            var card = cards[i]
            var key = card.title
            var series = nextMap[key] ? nextMap[key].slice(0) : []
            if (card.rawPrimary !== null && typeof card.rawPrimary !== "undefined")
                series.push(card.rawPrimary)
            if (series.length > 30)
                series = series.slice(series.length - 30)
            nextMap[key] = series
            card.history = series
        }
        historyMap = nextMap
    }

    function maybeNotifyAlerts() {
        var alerts = Utils.collectAlertSensors(baseRows)
        if (alerts.length === 0) {
            topAlertText = ""
            lastAlertSignature = ""
            return
        }

        topAlertText = alerts[0].name + " " + alerts[0].value
        var signature = alerts[0].path + "|" + alerts[0].severity + "|" + alerts[0].value
        if (!plasmoid.configuration.notificationsEnabled || signature === lastAlertSignature)
            return

        lastAlertSignature = signature
        notification.title = alerts[0].severity === "critical" ? "Critical sensor alert" : "Sensor warning"
        notification.text = alerts[0].name + " at " + alerts[0].value
        notification.sendEvent()
    }

    Plasma5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []

        function exec(cmd, callback) {
            listeners[cmd] = callback
            connectSource(cmd)
        }

        property var listeners: ({})

        onNewData: function(sourceName, data) {
            var callback = listeners[sourceName]
            if (callback) {
                callback(sourceName, data["stdout"], data["stderr"], data["exit code"])
                delete listeners[sourceName]
            }
            disconnectSource(sourceName)
        }
    }

    Timer {
        id: refreshTimer
        interval: Math.max(2, plasmoid.configuration.refreshSeconds) * 1000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    Connections {
        target: plasmoid.configuration
        function onRefreshSecondsChanged() {
            refreshTimer.interval = Math.max(2, plasmoid.configuration.refreshSeconds) * 1000
        }
        function onSourceChanged() {
            root.refresh()
        }
        function onWarnTempCChanged() { root.refresh() }
        function onCriticalTempCChanged() { root.refresh() }
        function onWarnLoadPctChanged() { root.refresh() }
        function onCriticalLoadPctChanged() { root.refresh() }
    }

    Notification {
        id: notification
        componentName: "com.github.loofi.hwremotemonitor"
        eventId: "sensor-alert"
        appName: "HWMonitor Remote"
    }

    Component.onCompleted: refresh()

    compactRepresentation: Local.CompactRepresentation { }
    fullRepresentation: Local.FullRepresentation { }
}
