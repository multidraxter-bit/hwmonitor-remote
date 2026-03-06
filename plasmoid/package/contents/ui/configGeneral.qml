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

    QQC2.SpinBox {
        Kirigami.FormData.label: "Warn temp C:"
        from: 50
        to: 110
        value: plasmoid.configuration.warnTempC
        editable: true
        onValueModified: plasmoid.configuration.warnTempC = value
    }

    QQC2.SpinBox {
        Kirigami.FormData.label: "Critical temp C:"
        from: 60
        to: 120
        value: plasmoid.configuration.criticalTempC
        editable: true
        onValueModified: plasmoid.configuration.criticalTempC = value
    }

    QQC2.SpinBox {
        Kirigami.FormData.label: "Warn load %:"
        from: 50
        to: 100
        value: plasmoid.configuration.warnLoadPct
        editable: true
        onValueModified: plasmoid.configuration.warnLoadPct = value
    }

    QQC2.SpinBox {
        Kirigami.FormData.label: "Critical load %:"
        from: 60
        to: 100
        value: plasmoid.configuration.criticalLoadPct
        editable: true
        onValueModified: plasmoid.configuration.criticalLoadPct = value
    }

    QQC2.CheckBox {
        Kirigami.FormData.label: "Notifications:"
        checked: plasmoid.configuration.notificationsEnabled
        text: "Notify on warning and critical sensors"
        onToggled: plasmoid.configuration.notificationsEnabled = checked
    }
}
