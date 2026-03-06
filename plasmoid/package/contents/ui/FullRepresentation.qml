import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "." as Local

Item {
    implicitWidth: Kirigami.Units.gridUnit * 56
    implicitHeight: Kirigami.Units.gridUnit * 32

    readonly property color panelBg: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.96)
    readonly property color sectionBg: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.88)
    readonly property color gridLine: Qt.rgba(1, 1, 1, 0.08)

    function badgeColor(severity) {
        if (severity === "critical")
            return Kirigami.Theme.negativeTextColor
        if (severity === "warn")
            return Kirigami.Theme.neutralTextColor
        if (severity === "cool")
            return Kirigami.Theme.positiveTextColor
        return Kirigami.Theme.highlightColor
    }

    function chipModel() {
        return [
            { key: "all", label: "All", count: root.sensorCounts.total },
            { key: "temperature", label: "Temp", count: root.sensorCounts.temperature },
            { key: "load", label: "Load", count: root.sensorCounts.load },
            { key: "cooling", label: "Fan", count: root.sensorCounts.cooling },
            { key: "power", label: "Power", count: root.sensorCounts.power },
            { key: "clock", label: "Clock", count: root.sensorCounts.clock },
            { key: "storage", label: "Drive", count: root.sensorCounts.storage }
        ]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        Rectangle {
            Layout.fillWidth: true
            radius: 6
            color: panelBg
            border.width: 1
            border.color: gridLine
            implicitHeight: 72

            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    QQC2.Label {
                        text: "HWMonitor Remote"
                        font.bold: true
                        font.pixelSize: 17
                    }

                    QQC2.Label {
                        Layout.fillWidth: true
                        text: root.sourceLabel
                        color: Kirigami.Theme.disabledTextColor
                        elide: Text.ElideMiddle
                        font.pixelSize: 12
                    }

                    QQC2.Label {
                        Layout.fillWidth: true
                        text: root.refreshOk ? root.statusText : (root.lastError ? root.lastError : root.statusText)
                        color: root.refreshOk ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.negativeTextColor
                        elide: Text.ElideRight
                        font.pixelSize: 12
                    }
                }

                Repeater {
                    model: root.summaryCards

                    delegate: Rectangle {
                        required property var modelData
                        Layout.preferredWidth: 132
                        Layout.fillHeight: true
                        radius: 4
                        color: sectionBg
                        border.width: 1
                        border.color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.35)

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 2

                            QQC2.Label {
                                text: modelData.title
                                font.bold: true
                                font.pixelSize: 11
                                color: Kirigami.Theme.disabledTextColor
                            }

                            QQC2.Label {
                                text: modelData.primary
                                font.bold: true
                                font.pixelSize: 18
                                color: badgeColor(modelData.severity)
                            }

                            Local.Sparkline {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 16
                                values: modelData.history || []
                                lineColor: badgeColor(modelData.severity)
                            }

                            QQC2.Label {
                                Layout.fillWidth: true
                                text: modelData.secondary
                                font.pixelSize: 10
                                color: Kirigami.Theme.disabledTextColor
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                QQC2.Button {
                    text: "Refresh"
                    onClicked: root.refresh()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            Rectangle {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                radius: 6
                color: panelBg
                border.width: 1
                border.color: gridLine

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 8

                    QQC2.Label {
                        text: "Focused Overview"
                        font.bold: true
                        font.pixelSize: 13
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 4

                        Repeater {
                            model: root.focusSensors

                            delegate: Rectangle {
                                required property var modelData
                                radius: 4
                                color: sectionBg
                                border.width: 1
                                border.color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.35)
                                implicitWidth: chipRow.implicitWidth + 12
                                implicitHeight: chipRow.implicitHeight + 8

                                RowLayout {
                                    id: chipRow
                                    anchors.centerIn: parent
                                    spacing: 5

                                    QQC2.Label {
                                        text: modelData.label
                                        font.bold: true
                                        font.pixelSize: 11
                                    }

                                    QQC2.Label {
                                        text: modelData.value
                                        color: badgeColor(modelData.severity)
                                        font.bold: true
                                        font.pixelSize: 11
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 4
                        color: sectionBg
                        border.width: 1
                        border.color: gridLine

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 6

                            QQC2.Label {
                                text: "CPU Core Temperatures"
                                font.bold: true
                                font.pixelSize: 12
                            }

                            QQC2.ScrollView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true

                                ListView {
                                    model: root.cpuCoreRows
                                    spacing: 3

                                    delegate: Rectangle {
                                        required property var modelData
                                        width: ListView.view.width
                                        height: 24
                                        radius: 3
                                        color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.08)
                                        border.width: 1
                                        border.color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.28)

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            spacing: 6

                                            QQC2.Label {
                                                Layout.fillWidth: true
                                                text: modelData.name
                                                font.pixelSize: 11
                                                elide: Text.ElideRight
                                            }

                                            QQC2.Label {
                                                text: modelData.value
                                                font.bold: true
                                                font.pixelSize: 11
                                                color: badgeColor(modelData.severity)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: panelBg
                border.width: 1
                border.color: gridLine

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        QQC2.Label {
                            text: "Sensor Explorer"
                            font.bold: true
                            font.pixelSize: 13
                        }

                        QQC2.Label {
                            Layout.fillWidth: true
                            text: root.topAlertText
                            visible: root.topAlertText.length > 0
                            horizontalAlignment: Text.AlignRight
                            color: root.overallLevel === "critical" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor
                            elide: Text.ElideLeft
                            font.pixelSize: 11
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 4
                        color: sectionBg
                        border.width: 1
                        border.color: gridLine
                        implicitHeight: 104

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 6

                            QQC2.Label {
                                text: "Pinned Favorites"
                                font.bold: true
                                font.pixelSize: 12
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                QQC2.Label { Layout.preferredWidth: 120; text: "Name"; font.bold: true; font.pixelSize: 10 }
                                QQC2.Label { Layout.fillWidth: true; text: "Sensor"; font.bold: true; font.pixelSize: 10 }
                                QQC2.Label { Layout.preferredWidth: 84; text: "Value"; font.bold: true; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                                QQC2.Label { Layout.preferredWidth: 84; text: "Min"; font.bold: true; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                                QQC2.Label { Layout.preferredWidth: 84; text: "Max"; font.bold: true; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                            }

                            Repeater {
                                model: root.favoriteRows

                                delegate: Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    height: 22
                                    radius: 3
                                    color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.08)

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 6
                                        anchors.rightMargin: 6
                                        spacing: 6

                                        QQC2.Label { Layout.preferredWidth: 120; text: modelData.label; font.bold: true; font.pixelSize: 10; elide: Text.ElideRight }
                                        QQC2.Label { Layout.fillWidth: true; text: modelData.name; font.pixelSize: 10; elide: Text.ElideRight }
                                        QQC2.Label { Layout.preferredWidth: 84; text: modelData.value; font.pixelSize: 10; horizontalAlignment: Text.AlignRight; color: badgeColor(modelData.severity) }
                                        QQC2.Label { Layout.preferredWidth: 84; text: modelData.min; font.pixelSize: 10; horizontalAlignment: Text.AlignRight; color: Kirigami.Theme.disabledTextColor }
                                        QQC2.Label { Layout.preferredWidth: 84; text: modelData.max; font.pixelSize: 10; horizontalAlignment: Text.AlignRight; color: Kirigami.Theme.disabledTextColor }
                                    }
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        QQC2.TextField {
                            Layout.fillWidth: true
                            placeholderText: "Filter sensors"
                            text: root.searchText
                            font.pixelSize: 11
                            onTextChanged: {
                                root.searchText = text
                                root.applyFilters()
                            }
                        }

                        QQC2.Button {
                            text: "Clear"
                            enabled: root.searchText.length > 0
                            onClicked: {
                                root.searchText = ""
                                root.applyFilters()
                            }
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 4

                        Repeater {
                            model: chipModel()

                            delegate: QQC2.Button {
                                required property var modelData
                                text: modelData.label + " " + modelData.count
                                flat: root.activeCategory !== modelData.key
                                highlighted: root.activeCategory === modelData.key
                                onClicked: {
                                    root.activeCategory = modelData.key
                                    root.applyFilters()
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 4
                        color: sectionBg
                        border.width: 1
                        border.color: gridLine

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                QQC2.Label { Layout.preferredWidth: 400; text: "Sensor"; font.bold: true; font.pixelSize: 10 }
                                QQC2.Label { Layout.preferredWidth: 72; text: "Value"; font.bold: true; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                                QQC2.Label { Layout.preferredWidth: 72; text: "Min"; font.bold: true; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                                QQC2.Label { Layout.preferredWidth: 72; text: "Max"; font.bold: true; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                            }

                            QQC2.ScrollView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true

                                ListView {
                                    id: listView
                                    model: root.visibleRows
                                    spacing: 2
                                    clip: true

                                    delegate: Rectangle {
                                        required property var modelData
                                        width: listView.width
                                        height: 22
                                        radius: 2
                                        color: modelData.kind === "sensor" ? "transparent" : Qt.rgba(1, 1, 1, 0.04)

                                        Rectangle {
                                            visible: modelData.kind === "sensor"
                                            anchors.left: parent.left
                                            anchors.top: parent.top
                                            anchors.bottom: parent.bottom
                                            width: 3
                                            color: badgeColor(modelData.severity)
                                        }

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 6
                                            anchors.rightMargin: 6
                                            spacing: 6

                                            QQC2.Label {
                                                Layout.preferredWidth: 400
                                                leftPadding: modelData.indent * 14
                                                text: (modelData.hasChildren ? (modelData.expanded ? "▼ " : "▶ ") : "") + modelData.name
                                                font.bold: modelData.kind !== "sensor"
                                                font.pixelSize: 10
                                                elide: Text.ElideRight
                                            }

                                            QQC2.Label {
                                                Layout.preferredWidth: 72
                                                text: modelData.value
                                                horizontalAlignment: Text.AlignRight
                                                font.pixelSize: 10
                                                color: modelData.kind === "sensor" ? badgeColor(modelData.severity) : Kirigami.Theme.disabledTextColor
                                                font.bold: modelData.kind === "sensor" && modelData.severity !== "normal"
                                            }

                                            QQC2.Label {
                                                Layout.preferredWidth: 72
                                                text: modelData.min
                                                horizontalAlignment: Text.AlignRight
                                                font.pixelSize: 10
                                                color: Kirigami.Theme.disabledTextColor
                                            }

                                            QQC2.Label {
                                                Layout.preferredWidth: 72
                                                text: modelData.max
                                                horizontalAlignment: Text.AlignRight
                                                font.pixelSize: 10
                                                color: Kirigami.Theme.disabledTextColor
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            enabled: modelData.hasChildren
                                            onClicked: root.toggleExpanded(modelData.path)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
