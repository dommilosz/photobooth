import QtQuick 2.12
import QtQuick.VirtualKeyboard 2.4

Item {
    id: root
    width: parent ? parent.width : 800
    height: inputPanel.active ? inputPanel.height : 0
    clip: true

    InputPanel {
        id: inputPanel
        z: 89
        x: 0
        y: 0
        width: parent.width
    }
}
