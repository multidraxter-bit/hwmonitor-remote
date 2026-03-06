import QtQuick
import org.kde.kirigami as Kirigami

Canvas {
    id: canvas
    property var values: []
    property color lineColor: Kirigami.Theme.highlightColor

    onValuesChanged: requestPaint()
    onLineColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()

        if (!values || values.length < 2)
            return

        var min = values[0]
        var max = values[0]
        for (var i = 1; i < values.length; i++) {
            min = Math.min(min, values[i])
            max = Math.max(max, values[i])
        }
        if (max === min)
            max = min + 1

        ctx.strokeStyle = lineColor
        ctx.lineWidth = 2
        ctx.beginPath()

        for (var p = 0; p < values.length; p++) {
            var x = (width - 2) * p / Math.max(1, values.length - 1) + 1
            var y = height - (((values[p] - min) / (max - min)) * (height - 4)) - 2
            if (p === 0)
                ctx.moveTo(x, y)
            else
                ctx.lineTo(x, y)
        }
        ctx.stroke()
    }
}
