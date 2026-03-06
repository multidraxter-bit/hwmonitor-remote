import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    anchors.left: parent.left
    anchors.right: parent.right

    QQC2.TextField {
        id: sourceField
        Kirigami.FormData.label: "Source:"
        text: plasmoid.configuration.source
        placeholderText: "ssh://loofi@192.168.1.3 or http://host:8086/data.json"
        onTextChanged: plasmoid.configuration.source = text
    }

    QQC2.SpinBox {
        id: refreshBox
        Kirigami.FormData.label: "Refresh:"
        from: 2
        to: 60
        value: plasmoid.configuration.refreshSeconds
        editable: true
        onValueModified: plasmoid.configuration.refreshSeconds = value
    }
}
