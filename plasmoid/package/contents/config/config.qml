import QtQuick
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    implicitWidth: 480
    implicitHeight: 240

    ConfigGeneral {
        anchors.fill: parent
    }
}
