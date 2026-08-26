from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class ToolboxCard(QWidget):
    """Compact Cello-style result row: icon, strong title, one-line context, badge."""

    def __init__(self, icon: QIcon, title: str, subtitle: str, badge: str = "", parent=None, image_size: int = 34) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 5, 7, 5)
        row.setSpacing(9)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(QSize(image_size, image_size)))
        icon_label.setFixedSize(image_size + 4, image_size + 4)
        icon_label.setAlignment(Qt.AlignCenter)
        row.addWidget(icon_label)

        text_host = QWidget()
        text_host.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        text = QVBoxLayout(text_host)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        title_label = QLabel(title)
        tf = title_label.font(); tf.setBold(True); title_label.setFont(tf)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("ToolboxSubtitle")
        subtitle_label.setTextFormat(Qt.PlainText)
        subtitle_label.setMaximumHeight(18)
        text.addWidget(title_label)
        text.addWidget(subtitle_label)
        row.addWidget(text_host, 1)

        if badge:
            badge_label = QLabel(badge)
            badge_label.setObjectName("ToolboxBadge")
            badge_label.setAlignment(Qt.AlignCenter)
            row.addWidget(badge_label)


class LinePlotWidget(QWidget):
    """Small dependency-free scientific line plot for trajectory analyses."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._x = []
        self._y = []
        self._x_label = "x"
        self._y_label = "y"
        self._title = ""
        self.setMinimumHeight(180)

    def set_series(self, x, y, *, title: str = "", x_label: str = "x", y_label: str = "y") -> None:
        self._x = [float(v) for v in x]
        self._y = [float(v) for v in y]
        self._title = title
        self._x_label = x_label
        self._y_label = y_label
        self.update()

    def clear(self) -> None:
        self._x = []; self._y = []; self._title = ""; self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(48, 28, -18, -34)
        p.fillRect(self.rect(), self.palette().base())
        axis = QPen(self.palette().text().color()); axis.setWidthF(1.0); p.setPen(axis)
        p.drawLine(rect.bottomLeft(), rect.bottomRight()); p.drawLine(rect.bottomLeft(), rect.topLeft())
        if self._title:
            p.drawText(QRectF(8, 4, self.width()-16, 20), Qt.AlignCenter, self._title)
        p.drawText(QRectF(rect.left(), rect.bottom()+8, rect.width(), 20), Qt.AlignCenter, self._x_label)
        p.save(); p.translate(14, rect.center().y()); p.rotate(-90); p.drawText(QRectF(-rect.height()/2, -10, rect.height(), 20), Qt.AlignCenter, self._y_label); p.restore()
        if len(self._x) < 2 or len(self._x) != len(self._y):
            p.drawText(rect, Qt.AlignCenter, "No analysis data")
            p.end(); return
        xmin, xmax = min(self._x), max(self._x); ymin, ymax = min(self._y), max(self._y)
        if xmax == xmin: xmax = xmin + 1.0
        if ymax == ymin: ymax = ymin + 1.0
        pad = 0.08*(ymax-ymin); ymin -= pad; ymax += pad
        def pt(x, y):
            sx = rect.left() + (x-xmin)/(xmax-xmin)*rect.width()
            sy = rect.bottom() - (y-ymin)/(ymax-ymin)*rect.height()
            return QPointF(sx, sy)
        path = QPainterPath(pt(self._x[0], self._y[0]))
        for x, y in zip(self._x[1:], self._y[1:]): path.lineTo(pt(x,y))
        line = QPen(QColor("#2f6f9f")); line.setWidthF(2.0); p.setPen(line); p.drawPath(path)
        p.setPen(axis)
        p.drawText(QRectF(rect.left()-42, rect.top()-7, 38, 16), Qt.AlignRight, f"{ymax:.3g}")
        p.drawText(QRectF(rect.left()-42, rect.bottom()-7, 38, 16), Qt.AlignRight, f"{ymin:.3g}")
        p.drawText(QRectF(rect.left()-5, rect.bottom()+8, 60, 18), Qt.AlignLeft, f"{xmin:.3g}")
        p.drawText(QRectF(rect.right()-55, rect.bottom()+8, 60, 18), Qt.AlignRight, f"{xmax:.3g}")
        p.end()


class HeatmapWidget(QWidget):
    """Dependency-free 2D heatmap for occupancy/free-energy surfaces."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._z = None
        self._x = []
        self._y = []
        self._title = ""
        self._x_label = "x"
        self._y_label = "y"
        self._legend = ""
        self.setMinimumHeight(250)

    def set_data(self, x, y, z, *, title: str = "", x_label: str = "x", y_label: str = "y", legend: str = "") -> None:
        import numpy as np
        self._x = np.asarray(x, dtype=float)
        self._y = np.asarray(y, dtype=float)
        self._z = np.asarray(z, dtype=float)
        self._title = title
        self._x_label = x_label
        self._y_label = y_label
        self._legend = legend
        self.update()

    def clear(self) -> None:
        self._z = None
        self._x = []
        self._y = []
        self._title = ""
        self.update()

    @staticmethod
    def _color(t: float):
        from PySide6.QtGui import QColor
        # Perceptually ordered blue -> cyan -> yellow -> red without external plotting deps.
        t = max(0.0, min(1.0, float(t)))
        stops = [
            (0.00, (40, 65, 120)),
            (0.33, (56, 153, 190)),
            (0.66, (236, 204, 92)),
            (1.00, (184, 55, 45)),
        ]
        for (a, ca), (b, cb) in zip(stops[:-1], stops[1:]):
            if a <= t <= b:
                u = (t-a)/(b-a)
                rgb = tuple(round(ca[i] + u*(cb[i]-ca[i])) for i in range(3))
                return QColor(*rgb)
        return QColor(*stops[-1][1])

    def paintEvent(self, event) -> None:  # noqa: ANN001
        import numpy as np
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainter, QPen

        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), self.palette().base())
        rect = self.rect().adjusted(62, 32, -70, -42)
        p.setPen(QPen(self.palette().text().color()))
        if self._title:
            p.drawText(QRectF(8, 4, self.width()-16, 22), Qt.AlignCenter, self._title)
        if self._z is None or getattr(self._z, "ndim", 0) != 2 or self._z.size == 0:
            p.drawText(rect, Qt.AlignCenter, "No landscape data")
            p.end(); return

        finite = self._z[np.isfinite(self._z)]
        if finite.size == 0:
            p.drawText(rect, Qt.AlignCenter, "No occupied histogram bins")
            p.end(); return
        zmin = float(np.min(finite)); zmax = float(np.max(finite))
        if zmax <= zmin: zmax = zmin + 1.0
        nx, ny = self._z.shape
        cw = rect.width()/max(1, nx); ch = rect.height()/max(1, ny)
        for ix in range(nx):
            for iy in range(ny):
                val = self._z[ix, iy]
                cell = QRectF(rect.left()+ix*cw, rect.bottom()-(iy+1)*ch, cw+0.6, ch+0.6)
                if not np.isfinite(val):
                    p.fillRect(cell, self.palette().alternateBase())
                else:
                    p.fillRect(cell, self._color((float(val)-zmin)/(zmax-zmin)))
        p.setPen(QPen(self.palette().text().color()))
        p.drawRect(rect)
        p.drawText(QRectF(rect.left(), rect.bottom()+10, rect.width(), 20), Qt.AlignCenter, self._x_label)
        p.save(); p.translate(17, rect.center().y()); p.rotate(-90); p.drawText(QRectF(-rect.height()/2, -10, rect.height(), 20), Qt.AlignCenter, self._y_label); p.restore()
        if len(self._x):
            p.drawText(QRectF(rect.left()-10, rect.bottom()+8, 65, 20), Qt.AlignLeft, f"{float(self._x[0]):.3g}")
            p.drawText(QRectF(rect.right()-55, rect.bottom()+8, 65, 20), Qt.AlignRight, f"{float(self._x[-1]):.3g}")
        if len(self._y):
            p.drawText(QRectF(0, rect.bottom()-8, rect.left()-7, 18), Qt.AlignRight, f"{float(self._y[0]):.3g}")
            p.drawText(QRectF(0, rect.top()-8, rect.left()-7, 18), Qt.AlignRight, f"{float(self._y[-1]):.3g}")

        # compact legend
        lx = rect.right()+18; ly = rect.top(); lh = rect.height(); lw = 15
        steps = max(20, int(lh))
        for i in range(steps):
            t = i/max(1, steps-1)
            yy = ly + (1.0-t)*lh
            p.fillRect(QRectF(lx, yy, lw, lh/steps+1), self._color(t))
        p.setPen(QPen(self.palette().text().color())); p.drawRect(QRectF(lx, ly, lw, lh))
        p.drawText(QRectF(lx+20, ly-8, 48, 18), Qt.AlignLeft, f"{zmax:.3g}")
        p.drawText(QRectF(lx+20, ly+lh-10, 48, 18), Qt.AlignLeft, f"{zmin:.3g}")
        if self._legend:
            p.save(); p.translate(lx+54, ly+lh/2); p.rotate(-90); p.drawText(QRectF(-lh/2, -10, lh, 20), Qt.AlignCenter, self._legend); p.restore()
        p.end()
