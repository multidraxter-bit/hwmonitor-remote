import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "." as Local

Item {
    implicitWidth: Kirigami.Units.gridUnit * 32
    implicitHeight: Kirigami.Units.gridUnit * 34

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
            { key: "temperature", label: "Temps", count: root.sensorCounts.temperature },
            { key: "load", label: "Load", count: root.sensorCounts.load },
            { key: "cooling", label: "Fans", count: root.sensorCounts.cooling },
            { key: "power", label: "Power", count: root.sensorCounts.power },
            { key: "clock", label: "Clock", count: root.sensorCounts.clock },
            { key: "storage", label: "Storage", count: root.sensorCounts.storage }
        ]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        Rectangle {
            Layout.fillWidth: true
            radius: 12
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.92)
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.08)
            implicitHeight: headerLayout.implicitHeight + 18

            RowLayout {
                id: headerLayout
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    QQC2.Label {
                        text: "HWMonitor Remote"
                        font.bold: true
                        font.pointSize: 12
                    }

                    QQC2.Label {
                        Layout.fillWidth: true
                        text: root.sourceLabel
                        color: Kirigami.Theme.disabledTextColor
                        elide: Text.ElideMiddle
                    }

                    QQC2.Label {
                        Layout.fillWidth: true
                        text: root.refreshOk ? root.statusText : (root.lastError ? root.lastError : root.statusText)
                        color: root.refreshOk ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.negativeTextColor
                        elide: Text.ElideRight
                    }
                }

                Rectangle {
                    radius: 999
                    color: root.refreshOk ? Qt.rgba(Kirigami.Theme.positiveTextColor.r, Kirigami.Theme.positiveTextColor.g, Kirigami.Theme.positiveTextColor.b, 0.15)
                                          : Qt.rgba(Kirigami.Theme.negativeTextColor.r, Kirigami.Theme.negativeTextColor.g, Kirigami.Theme.negativeTextColor.b, 0.15)
                    border.width: 1
                    border.color: root.refreshOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                    implicitWidth: badgeLabel.implicitWidth + 18
                    implicitHeight: badgeLabel.implicitHeight + 8

                    QQC2.Label {
                        id: badgeLabel
                        anchors.centerIn: parent
                        text: root.refreshOk ? "LIVE" : "ERROR"
                        font.bold: true
                        color: root.refreshOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                    }
                }

                QQC2.Button {
                    text: "Refresh"
                    onClicked: root.refresh()
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 8
            rowSpacing: 8

            Repeater {
                model: root.summaryCards

                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.minimumHeight: 84
                    radius: 14
                    color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.86)
                    border.width: 1
                    border.color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.4)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        QQC2.Label {
                            text: modelData.title
                            color: Kirigami.Theme.disabledTextColor
                            font.bold: true
                        }

                        QQC2.Label {
                            text: modelData.primary
                            font.pointSize: 16
                            font.bold: true
                            color: badgeColor(modelData.severity)
                        }

                        Local.Sparkline {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 22
                            values: modelData.history || []
                            lineColor: badgeColor(modelData.severity)
                        }

                        QQC2.Label {
                            Layout.fillWidth: true
                            text: modelData.secondary
                            color: Kirigami.Theme.disabledTextColor
                            elide: Text.ElideRight
                        }

                        QQC2.Label {
                            Layout.fillWidth: true
                            visible: modelData.tertiary && modelData.tertiary.length > 0
                            text: modelData.tertiary
                            color: Kirigami.Theme.disabledTextColor
                            elide: Text.ElideRight
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 12
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.82)
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.08)
            implicitHeight: focusLayout.implicitHeight + 18

            ColumnLayout {
                id: focusLayout
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                QQC2.Label {
                    text: "Focus Sensors"
                    font.bold: true
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 6

                    Repeater {
                        model: root.focusSensors

                        delegate: Rectangle {
                            required property var modelData
                            radius: 999
                            color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.14)
                            border.width: 1
                            border.color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.45)
                            implicitWidth: chipRow.implicitWidth + 18
                            implicitHeight: chipRow.implicitHeight + 8

                            RowLayout {
                                id: chipRow
                                anchors.centerIn: parent
                                spacing: 6

                                QQC2.Label {
                                    text: modelData.label
                                    font.bold: true
                                }

                                QQC2.Label {
                                    text: modelData.value
                                    color: badgeColor(modelData.severity)
                                    font.bold: true
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 12
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.82)
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.08)
            visible: root.cpuCoreRows.length > 0
            implicitHeight: coreLayout.implicitHeight + 18

            ColumnLayout {
                id: coreLayout
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                QQC2.Label {
                    text: "Hottest CPU Cores"
                    font.bold: true
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 8
                    rowSpacing: 6

                    Repeater {
                        model: root.cpuCoreRows

                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            radius: 10
                            color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.10)
                            border.width: 1
                            border.color: Qt.rgba(badgeColor(modelData.severity).r, badgeColor(modelData.severity).g, badgeColor(modelData.severity).b, 0.35)
                            implicitHeight: coreRow.implicitHeight + 10

                            RowLayout {
                                id: coreRow
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 6

                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: modelData.name
                                    elide: Text.ElideRight
                                }

                                QQC2.Label {
                                    text: modelData.value
                                    color: badgeColor(modelData.severity)
                                    font.bold: true
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            QQC2.TextField {
                Layout.fillWidth: true
                placeholderText: "Search sensors, hardware, or categories"
                text: root.searchText
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
            spacing: 6

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

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            QQC2.Label {
                Layout.preferredWidth: 316
                text: "Sensor"
                font.bold: true
            }
            QQC2.Label {
                Layout.preferredWidth: 96
                text: "Value"
                font.bold: true
                horizontalAlignment: Text.AlignRight
            }
            QQC2.Label {
                Layout.preferredWidth: 96
                text: "Min"
                font.bold: true
                horizontalAlignment: Text.AlignRight
            }
            QQC2.Label {
                Layout.preferredWidth: 96
                text: "Max"
                font.bold: true
                horizontalAlignment: Text.AlignRight
            }
        }

        QQC2.ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ListView {
                id: listView
                model: root.visibleRows
                spacing: 4
                clip: true

                delegate: Rectangle {
                    required property var modelData
                    width: listView.width
                    height: 28
                    radius: 8
                    color: modelData.kind === "sensor"
                        ? Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.68)
                        : Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.92)
                    border.width: modelData.kind === "sensor" ? 0 : 1
                    border.color: Qt.rgba(1, 1, 1, 0.08)

                    Rectangle {
                        visible: modelData.kind === "sensor"
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 4
                        radius: 8
                        color: badgeColor(modelData.severity)
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 8

                        QQC2.Label {
                            Layout.preferredWidth: 316
                            leftPadding: modelData.indent * 16
                            text: (modelData.hasChildren ? (modelData.expanded ? "▼ " : "▶ ") : "") + modelData.name
                            font.bold: modelData.kind !== "sensor"
                            elide: Text.ElideRight
                        }

                        QQC2.Label {
                            Layout.preferredWidth: 96
                            text: modelData.value
                            horizontalAlignment: Text.AlignRight
                            color: modelData.kind === "sensor" ? badgeColor(modelData.severity) : Kirigami.Theme.disabledTextColor
                            font.bold: modelData.kind === "sensor" && modelData.severity !== "normal"
                        }

                        QQC2.Label {
                            Layout.preferredWidth: 96
                            text: modelData.min
                            horizontalAlignment: Text.AlignRight
                            color: Kirigami.Theme.disabledTextColor
                        }

                        QQC2.Label {
                            Layout.preferredWidth: 96
                            text: modelData.max
                            horizontalAlignment: Text.AlignRight
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
