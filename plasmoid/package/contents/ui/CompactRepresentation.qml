import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    implicitWidth: root.inPanel ? Kirigami.Units.gridUnit * 12 : Kirigami.Units.gridUnit * 14
    implicitHeight: Kirigami.Units.gridUnit * 4

    MouseArea {
        anchors.fill: parent
        onClicked: Plasmoid.expanded = !Plasmoid.expanded
    }

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: root.overallLevel === "critical"
            ? Qt.rgba(Kirigami.Theme.negativeTextColor.r, Kirigami.Theme.negativeTextColor.g, Kirigami.Theme.negativeTextColor.b, 0.16)
            : (root.overallLevel === "warn"
                ? Qt.rgba(Kirigami.Theme.neutralTextColor.r, Kirigami.Theme.neutralTextColor.g, Kirigami.Theme.neutralTextColor.b, 0.16)
                : Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.78))
        border.width: 1
        border.color: root.refreshOk
            ? (root.overallLevel === "critical"
                ? Kirigami.Theme.negativeTextColor
                : (root.overallLevel === "warn" ? Kirigami.Theme.neutralTextColor : Qt.rgba(Kirigami.Theme.positiveTextColor.r, Kirigami.Theme.positiveTextColor.g, Kirigami.Theme.positiveTextColor.b, 0.4)))
            : Qt.rgba(Kirigami.Theme.negativeTextColor.r, Kirigami.Theme.negativeTextColor.g, Kirigami.Theme.negativeTextColor.b, 0.45)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 6
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                QQC2.Label {
                    text: "HW"
                    font.bold: true
                }

                Rectangle {
                    radius: 999
                    color: root.refreshOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                    implicitWidth: 8
                    implicitHeight: 8
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    text: root.refreshOk ? (root.overallLevel === "critical" ? "Hot" : (root.overallLevel === "warn" ? "Warn" : "Live")) : "Err"
                    horizontalAlignment: Text.AlignRight
                    color: root.refreshOk ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.negativeTextColor
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: 0
                columnSpacing: 8

                QQC2.Label {
                    text: "CPU " + root.cpuSummary
                    font.bold: true
                    elide: Text.ElideRight
                }

                QQC2.Label {
                    text: "GPU " + root.gpuSummary
                    font.bold: true
                    elide: Text.ElideRight
                }

                QQC2.Label {
                    text: "Fan " + root.coolingSummary
                    color: Kirigami.Theme.disabledTextColor
                    elide: Text.ElideRight
                }

                QQC2.Label {
                    text: "SSD " + root.driveSummary
                    color: Kirigami.Theme.disabledTextColor
                    elide: Text.ElideRight
                }
            }

            QQC2.Label {
                Layout.fillWidth: true
                visible: root.topAlertText.length > 0
                text: root.topAlertText
                color: root.overallLevel === "critical" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor
                elide: Text.ElideRight
                font.pixelSize: 11
            }
        }
    }
}
