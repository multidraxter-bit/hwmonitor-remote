import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami
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
    property var visibleRows: []
    property var summaryCards: []
    property var sensorCounts: ({ total: 0, temperature: 0, load: 0, cooling: 0, power: 0, clock: 0, storage: 0, other: 0 })
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
                allRows = Utils.flattenTree(parsed)
                summaryCards = Utils.summarizeNode(parsed)
                sensorCounts = Utils.countSensors(allRows)
                cpuSummary = summaryCards.length > 0 ? summaryCards[0].primary : "--"
                gpuSummary = summaryCards.length > 1 ? summaryCards[1].primary : "--"
                coolingSummary = summaryCards.length > 2 ? summaryCards[2].primary : "--"
                driveSummary = summaryCards.length > 3 ? summaryCards[3].primary : "--"
                visibleRows = Utils.filterRows(allRows, searchText, activeCategory)
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
        visibleRows = Utils.filterRows(allRows, searchText, activeCategory)
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
    }

    Component.onCompleted: refresh()

    compactRepresentation: Local.CompactRepresentation { }
    fullRepresentation: Local.FullRepresentation { }
}
