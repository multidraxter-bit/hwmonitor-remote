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
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.78)
        border.width: 1
        border.color: root.refreshOk ? Qt.rgba(Kirigami.Theme.positiveTextColor.r, Kirigami.Theme.positiveTextColor.g, Kirigami.Theme.positiveTextColor.b, 0.4)
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
                    text: root.refreshOk ? "Live" : "Err"
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
        }
    }
}
