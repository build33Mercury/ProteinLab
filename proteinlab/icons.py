from __future__ import annotations

from functools import lru_cache
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


_COLORS = {
    "protein": "#6b4bbd",
    "builtin": "#4f6fb8",
    "my-protein": "#8a4fa3",
    "import": "#2f78a8",
    "create": "#3b7d5d",
    "pointer": "#4a5560",
    "reset": "#55748c",
    "representation": "#86604a",
    "info": "#3f6f91",
    "sequence": "#6c5c9e",
    "distance": "#3f7c70",
    "angle": "#8b633d",
    "dihedral": "#8b4c65",
    "prepare": "#3e7a8f",
    "energy": "#b36a22",
    "minimize": "#3c7a55",
    "md": "#4a68a8",
    "mutate": "#9b4b4b",
    "hbond": "#377f91",
    "contacts": "#6d6f9f",
    "surface": "#4c8c79",
    "align": "#6c6c75",
    "analysis": "#5d7292",
    "toolbox": "#375f82",
    "trajectory": "#4f6e9e",
    "rmsd": "#356f91",
    "rmsf": "#6b5a97",
    "environment": "#497a68",
    "mutant": "#994e5a",
    "explore": "#7557a8",
    "landscape": "#8a6a2f",
    "network": "#3f7f79",
    "ligand": "#7a5b9b",
    "interface": "#9a6841",
    "membrane": "#397d8a",
    "validate": "#4e7b58",
    "compare": "#7b586e",
    "fold": "#7652a7",
    "equation": "#436f95",
    "notebook": "#8a6a3f",
    "methods": "#4f7a65",
    "project": "#5d668e",
    "export": "#4c7794",
    "learn": "#6f7f45",
    "help": "#2f6f9f",
    "benchmark": "#4f7a65",
}


def _pen(color: QColor, width: float = 2.0, style=Qt.SolidLine) -> QPen:
    p = QPen(color)
    p.setWidthF(width)
    p.setStyle(style)
    p.setCapStyle(Qt.RoundCap)
    p.setJoinStyle(Qt.RoundJoin)
    return p


def make_icon(kind: str, size: int = 32) -> QIcon:
    """Return a crisp, dependency-free vector-like icon drawn with Qt primitives."""
    kind = kind or "analysis"
    c = QColor(_COLORS.get(kind, _COLORS["analysis"]))
    fg = QColor("#ffffff")
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    q = QPainter(pm)
    q.setRenderHint(QPainter.Antialiasing, True)
    s = float(size)

    # Quiet colored tile makes categories instantly readable without turning the UI into a dashboard.
    q.setPen(Qt.NoPen)
    tile = QColor(c)
    tile.setAlpha(235)
    q.setBrush(tile)
    q.drawRoundedRect(QRectF(2, 2, s - 4, s - 4), s * 0.19, s * 0.19)
    q.setBrush(Qt.NoBrush)
    q.setPen(_pen(fg, max(1.5, s / 15)))

    if kind in {"protein", "builtin", "my-protein"}:
        path = QPainterPath(QPointF(s * .22, s * .62))
        path.cubicTo(s * .29, s * .25, s * .46, s * .24, s * .49, s * .55)
        path.cubicTo(s * .52, s * .84, s * .70, s * .79, s * .76, s * .43)
        q.drawPath(path)
        q.drawLine(QPointF(s*.30,s*.41), QPointF(s*.67,s*.66))
        if kind == "builtin":
            q.drawEllipse(QPointF(s*.73,s*.25), s*.055, s*.055)
        if kind == "my-protein":
            q.drawLine(QPointF(s*.70,s*.24), QPointF(s*.82,s*.24))
            q.drawLine(QPointF(s*.76,s*.18), QPointF(s*.76,s*.30))
    elif kind == "import":
        q.drawRect(QRectF(s*.24, s*.25, s*.43, s*.48))
        q.drawLine(QPointF(s*.72,s*.55), QPointF(s*.72,s*.25))
        q.drawLine(QPointF(s*.62,s*.35), QPointF(s*.72,s*.25))
        q.drawLine(QPointF(s*.82,s*.35), QPointF(s*.72,s*.25))
    elif kind == "create":
        pts = [QPointF(s*.25,s*.61), QPointF(s*.45,s*.39), QPointF(s*.64,s*.60)]
        q.drawPolyline(QPolygonF(pts))
        for p in pts:
            q.drawEllipse(p, s*.055, s*.055)
        q.drawLine(QPointF(s*.70,s*.30), QPointF(s*.84,s*.30))
        q.drawLine(QPointF(s*.77,s*.23), QPointF(s*.77,s*.37))
    elif kind == "pointer":
        q.setBrush(fg)
        poly = QPolygonF([QPointF(s*.30,s*.20), QPointF(s*.68,s*.55), QPointF(s*.52,s*.58), QPointF(s*.61,s*.78), QPointF(s*.52,s*.82)])
        q.drawPolygon(poly)
    elif kind == "reset":
        q.drawArc(QRectF(s*.22,s*.22,s*.56,s*.56), 35*16, 285*16)
        q.drawLine(QPointF(s*.25,s*.34), QPointF(s*.22,s*.21))
        q.drawLine(QPointF(s*.25,s*.34), QPointF(s*.36,s*.29))
    elif kind == "representation":
        q.drawRect(QRectF(s*.27,s*.27,s*.40,s*.40))
        q.drawLine(QPointF(s*.27,s*.27), QPointF(s*.39,s*.18))
        q.drawLine(QPointF(s*.67,s*.27), QPointF(s*.79,s*.18))
        q.drawLine(QPointF(s*.67,s*.67), QPointF(s*.79,s*.58))
        q.drawLine(QPointF(s*.39,s*.18), QPointF(s*.79,s*.18))
        q.drawLine(QPointF(s*.79,s*.18), QPointF(s*.79,s*.58))
    elif kind == "info":
        q.drawEllipse(QRectF(s*.25,s*.20,s*.50,s*.58))
        q.drawPoint(QPointF(s*.50,s*.34))
        q.drawLine(QPointF(s*.50,s*.45), QPointF(s*.50,s*.65))
    elif kind == "sequence":
        for y, widths in [(0.31,(.25,.70)), (.50,(.20,.66)), (.69,(.30,.75))]:
            q.drawLine(QPointF(s*widths[0],s*y), QPointF(s*widths[1],s*y))
        q.drawEllipse(QPointF(s*.22,s*.31), s*.025, s*.025)
        q.drawEllipse(QPointF(s*.72,s*.50), s*.025, s*.025)
    elif kind == "distance":
        q.drawEllipse(QPointF(s*.25,s*.65), s*.055, s*.055)
        q.drawEllipse(QPointF(s*.75,s*.35), s*.055, s*.055)
        q.setPen(_pen(fg, max(1.5,s/17), Qt.DashLine))
        q.drawLine(QPointF(s*.30,s*.61), QPointF(s*.70,s*.39))
    elif kind == "angle":
        o=QPointF(s*.43,s*.67)
        q.drawLine(o,QPointF(s*.22,s*.30)); q.drawLine(o,QPointF(s*.80,s*.55))
        q.drawArc(QRectF(s*.37,s*.47,s*.25,s*.25), 25*16, 75*16)
    elif kind == "dihedral":
        q.drawPolyline(QPolygonF([QPointF(s*.18,s*.62),QPointF(s*.38,s*.36),QPointF(s*.58,s*.63),QPointF(s*.80,s*.35)]))
        q.drawArc(QRectF(s*.38,s*.35,s*.32,s*.32), 30*16, 190*16)
    elif kind == "prepare":
        q.drawLine(QPointF(s*.43,s*.20),QPointF(s*.43,s*.42)); q.drawLine(QPointF(s*.57,s*.20),QPointF(s*.57,s*.42))
        path=QPainterPath(QPointF(s*.43,s*.42)); path.lineTo(s*.27,s*.72); path.quadTo(s*.50,s*.84,s*.73,s*.72); path.lineTo(s*.57,s*.42)
        q.drawPath(path); q.drawLine(QPointF(s*.33,s*.62),QPointF(s*.67,s*.62))
    elif kind == "energy":
        q.setBrush(fg)
        q.drawPolygon(QPolygonF([QPointF(s*.55,s*.17),QPointF(s*.31,s*.53),QPointF(s*.47,s*.53),QPointF(s*.39,s*.82),QPointF(s*.71,s*.42),QPointF(s*.53,s*.42)]))
    elif kind == "minimize":
        path=QPainterPath(QPointF(s*.18,s*.32)); path.cubicTo(s*.33,s*.70,s*.40,s*.76,s*.50,s*.76); path.cubicTo(s*.60,s*.76,s*.67,s*.70,s*.82,s*.32); q.drawPath(path)
        q.drawLine(QPointF(s*.50,s*.20),QPointF(s*.50,s*.55)); q.drawLine(QPointF(s*.40,s*.46),QPointF(s*.50,s*.56)); q.drawLine(QPointF(s*.60,s*.46),QPointF(s*.50,s*.56))
    elif kind == "md":
        q.setBrush(fg); q.drawPolygon(QPolygonF([QPointF(s*.29,s*.24),QPointF(s*.29,s*.76),QPointF(s*.67,s*.50)])); q.setBrush(Qt.NoBrush)
        path=QPainterPath(QPointF(s*.60,s*.28)); path.cubicTo(s*.70,s*.35,s*.66,s*.43,s*.76,s*.50); path.cubicTo(s*.86,s*.58,s*.78,s*.65,s*.84,s*.72); q.drawPath(path)
    elif kind == "mutate":
        q.drawLine(QPointF(s*.23,s*.37),QPointF(s*.72,s*.37)); q.drawLine(QPointF(s*.62,s*.27),QPointF(s*.72,s*.37)); q.drawLine(QPointF(s*.62,s*.47),QPointF(s*.72,s*.37))
        q.drawLine(QPointF(s*.77,s*.64),QPointF(s*.28,s*.64)); q.drawLine(QPointF(s*.38,s*.54),QPointF(s*.28,s*.64)); q.drawLine(QPointF(s*.38,s*.74),QPointF(s*.28,s*.64))
    elif kind == "hbond":
        q.drawEllipse(QPointF(s*.25,s*.50),s*.07,s*.07); q.drawEllipse(QPointF(s*.75,s*.50),s*.07,s*.07); q.setPen(_pen(fg,max(1.4,s/18),Qt.DashLine)); q.drawLine(QPointF(s*.33,s*.50),QPointF(s*.67,s*.50))
    elif kind == "contacts":
        pts=[QPointF(s*.28,s*.28),QPointF(s*.72,s*.30),QPointF(s*.35,s*.70),QPointF(s*.70,s*.70)]
        for a,b in [(0,1),(0,2),(1,3),(2,3),(1,2)]: q.drawLine(pts[a],pts[b])
        q.setBrush(fg)
        for p in pts: q.drawEllipse(p,s*.045,s*.045)
    elif kind == "surface":
        path=QPainterPath(QPointF(s*.19,s*.55)); path.cubicTo(s*.22,s*.27,s*.42,s*.22,s*.50,s*.34); path.cubicTo(s*.60,s*.18,s*.82,s*.31,s*.80,s*.56); path.cubicTo(s*.84,s*.75,s*.58,s*.83,s*.47,s*.70); path.cubicTo(s*.34,s*.82,s*.18,s*.73,s*.19,s*.55); q.drawPath(path)
    elif kind == "align":
        q.drawRect(QRectF(s*.22,s*.28,s*.38,s*.38)); q.drawRect(QRectF(s*.40,s*.38,s*.38,s*.38))
    elif kind == "toolbox":
        q.drawRoundedRect(QRectF(s*.20,s*.22,s*.60,s*.56), s*.06, s*.06)
        q.drawLine(QPointF(s*.32,s*.36), QPointF(s*.68,s*.36)); q.drawLine(QPointF(s*.32,s*.50), QPointF(s*.68,s*.50)); q.drawLine(QPointF(s*.32,s*.64), QPointF(s*.56,s*.64))
        q.drawEllipse(QPointF(s*.25,s*.36),s*.025,s*.025); q.drawEllipse(QPointF(s*.25,s*.50),s*.025,s*.025); q.drawEllipse(QPointF(s*.25,s*.64),s*.025,s*.025)
    elif kind == "trajectory":
        path=QPainterPath(QPointF(s*.18,s*.58)); path.cubicTo(s*.28,s*.18,s*.42,s*.78,s*.54,s*.38); path.cubicTo(s*.64,s*.10,s*.72,s*.70,s*.83,s*.42); q.drawPath(path)
        for x,y in [(0.18,0.58),(0.54,0.38),(0.83,0.42)]: q.drawEllipse(QPointF(s*x,s*y),s*.035,s*.035)
    elif kind == "rmsd":
        q.drawLine(QPointF(s*.20,s*.72),QPointF(s*.20,s*.25)); q.drawLine(QPointF(s*.20,s*.72),QPointF(s*.82,s*.72))
        path=QPainterPath(QPointF(s*.24,s*.64)); path.lineTo(s*.40,s*.48); path.lineTo(s*.54,s*.55); path.lineTo(s*.68,s*.33); path.lineTo(s*.80,s*.39); q.drawPath(path)
    elif kind == "rmsf":
        q.drawLine(QPointF(s*.20,s*.72),QPointF(s*.20,s*.25)); q.drawLine(QPointF(s*.20,s*.72),QPointF(s*.82,s*.72))
        path=QPainterPath(QPointF(s*.24,s*.60)); path.cubicTo(s*.32,s*.30,s*.38,s*.74,s*.48,s*.50); path.cubicTo(s*.58,s*.18,s*.64,s*.76,s*.80,s*.36); q.drawPath(path)
    elif kind == "environment":
        q.drawEllipse(QRectF(s*.24,s*.30,s*.52,s*.40)); q.drawLine(QPointF(s*.50,s*.18),QPointF(s*.50,s*.30)); q.drawLine(QPointF(s*.50,s*.70),QPointF(s*.50,s*.82)); q.drawLine(QPointF(s*.14,s*.50),QPointF(s*.24,s*.50)); q.drawLine(QPointF(s*.76,s*.50),QPointF(s*.86,s*.50))
    elif kind == "mutant":
        q.drawLine(QPointF(s*.22,s*.35),QPointF(s*.74,s*.35)); q.drawLine(QPointF(s*.65,s*.26),QPointF(s*.74,s*.35)); q.drawLine(QPointF(s*.65,s*.44),QPointF(s*.74,s*.35)); q.drawEllipse(QPointF(s*.35,s*.65),s*.07,s*.07); q.drawEllipse(QPointF(s*.65,s*.65),s*.07,s*.07)
    elif kind == "explore":
        path=QPainterPath(QPointF(s*.18,s*.62)); path.cubicTo(s*.28,s*.24,s*.42,s*.74,s*.52,s*.40); path.cubicTo(s*.62,s*.12,s*.72,s*.70,s*.83,s*.30); q.drawPath(path)
        q.drawLine(QPointF(s*.22,s*.79),QPointF(s*.22,s*.22)); q.drawLine(QPointF(s*.22,s*.79),QPointF(s*.82,s*.79))
    elif kind == "landscape":
        for y0,w in [(0.68,0.60),(0.53,0.46),(0.38,0.30)]:
            q.drawEllipse(QRectF(s*(.50-w/2),s*(y0-w*.25),s*w,s*w*.5))
        q.drawEllipse(QPointF(s*.50,s*.44),s*.035,s*.035)
    elif kind == "network":
        pts=[QPointF(s*.25,s*.28),QPointF(s*.72,s*.25),QPointF(s*.50,s*.50),QPointF(s*.28,s*.74),QPointF(s*.75,s*.72)]
        for a,b in [(0,1),(0,2),(1,2),(2,3),(2,4),(3,4)]: q.drawLine(pts[a],pts[b])
        q.setBrush(fg)
        for pt in pts: q.drawEllipse(pt,s*.045,s*.045)
    elif kind == "ligand":
        pts=[QPointF(s*.28,s*.34),QPointF(s*.50,s*.22),QPointF(s*.72,s*.35),QPointF(s*.66,s*.64),QPointF(s*.38,s*.72),QPointF(s*.22,s*.55)]
        q.drawPolygon(QPolygonF(pts)); q.setBrush(fg)
        for pt in (pts[0],pts[2],pts[4]): q.drawEllipse(pt,s*.045,s*.045)
    elif kind == "interface":
        q.drawArc(QRectF(s*.16,s*.24,s*.44,s*.52),-70*16,140*16); q.drawArc(QRectF(s*.40,s*.24,s*.44,s*.52),110*16,140*16)
        q.setPen(_pen(fg,max(1.4,s/18),Qt.DashLine)); q.drawLine(QPointF(s*.44,s*.38),QPointF(s*.56,s*.38)); q.drawLine(QPointF(s*.44,s*.62),QPointF(s*.56,s*.62))
    elif kind == "membrane":
        for y in (.34,.66):
            q.drawLine(QPointF(s*.18,s*y),QPointF(s*.82,s*y))
            for x in (.25,.40,.55,.70): q.drawEllipse(QPointF(s*x,s*y),s*.035,s*.035)
        q.drawLine(QPointF(s*.47,s*.18),QPointF(s*.47,s*.82)); q.drawLine(QPointF(s*.55,s*.18),QPointF(s*.55,s*.82))
    elif kind == "validate":
        q.drawRoundedRect(QRectF(s*.22,s*.18,s*.56,s*.64),s*.08,s*.08); q.drawLine(QPointF(s*.34,s*.51),QPointF(s*.46,s*.63)); q.drawLine(QPointF(s*.46,s*.63),QPointF(s*.69,s*.36))
    elif kind == "compare":
        q.drawRect(QRectF(s*.18,s*.27,s*.42,s*.42)); q.drawRect(QRectF(s*.40,s*.35,s*.42,s*.42)); q.drawLine(QPointF(s*.27,s*.78),QPointF(s*.73,s*.20))
    elif kind == "fold":
        path=QPainterPath(QPointF(s*.20,s*.66)); path.cubicTo(s*.30,s*.20,s*.43,s*.78,s*.52,s*.42); path.cubicTo(s*.60,s*.14,s*.73,s*.63,s*.82,s*.30); q.drawPath(path); q.drawLine(QPointF(s*.28,s*.74),QPointF(s*.72,s*.74)); q.drawLine(QPointF(s*.62,s*.64),QPointF(s*.72,s*.74)); q.drawLine(QPointF(s*.62,s*.84),QPointF(s*.72,s*.74))
    elif kind == "equation":
        q.drawLine(QPointF(s*.23,s*.34),QPointF(s*.42,s*.34)); q.drawLine(QPointF(s*.23,s*.50),QPointF(s*.42,s*.50)); q.drawLine(QPointF(s*.54,s*.34),QPointF(s*.77,s*.34)); q.drawLine(QPointF(s*.54,s*.50),QPointF(s*.77,s*.50)); q.drawLine(QPointF(s*.30,s*.66),QPointF(s*.70,s*.66))
    elif kind == "notebook":
        q.drawRoundedRect(QRectF(s*.25,s*.18,s*.50,s*.64),s*.05,s*.05); q.drawLine(QPointF(s*.35,s*.34),QPointF(s*.66,s*.34)); q.drawLine(QPointF(s*.35,s*.49),QPointF(s*.66,s*.49)); q.drawLine(QPointF(s*.35,s*.64),QPointF(s*.58,s*.64))
    elif kind == "methods":
        q.drawRect(QRectF(s*.27,s*.20,s*.46,s*.60)); q.drawLine(QPointF(s*.35,s*.34),QPointF(s*.65,s*.34)); q.drawLine(QPointF(s*.35,s*.47),QPointF(s*.65,s*.47)); q.drawLine(QPointF(s*.35,s*.60),QPointF(s*.56,s*.60))
    elif kind == "project":
        q.drawRoundedRect(QRectF(s*.20,s*.28,s*.60,s*.48),s*.05,s*.05); q.drawLine(QPointF(s*.30,s*.28),QPointF(s*.38,s*.18)); q.drawLine(QPointF(s*.38,s*.18),QPointF(s*.62,s*.18)); q.drawLine(QPointF(s*.62,s*.18),QPointF(s*.70,s*.28))
    elif kind == "learn":
        q.drawEllipse(QRectF(s*.25,s*.20,s*.50,s*.50)); q.drawLine(QPointF(s*.50,s*.70),QPointF(s*.50,s*.82)); q.drawLine(QPointF(s*.39,s*.82),QPointF(s*.61,s*.82))
    elif kind == "help":
        q.drawEllipse(QRectF(s*.22,s*.18,s*.56,s*.56))
        path=QPainterPath(QPointF(s*.39,s*.36)); path.cubicTo(s*.40,s*.24,s*.62,s*.23,s*.64,s*.38); path.cubicTo(s*.65,s*.48,s*.51,s*.50,s*.50,s*.59); q.drawPath(path)
        q.drawEllipse(QPointF(s*.50,s*.70),s*.025,s*.025)
    elif kind == "benchmark":
        q.drawRoundedRect(QRectF(s*.20,s*.20,s*.60,s*.60),s*.06,s*.06)
        q.drawLine(QPointF(s*.30,s*.52),QPointF(s*.43,s*.65)); q.drawLine(QPointF(s*.43,s*.65),QPointF(s*.69,s*.35))
        q.drawLine(QPointF(s*.30,s*.30),QPointF(s*.70,s*.30))
    else:
        q.drawEllipse(QRectF(s*.24,s*.24,s*.52,s*.52)); q.drawLine(QPointF(s*.34,s*.50),QPointF(s*.66,s*.50))

    q.end()
    return QIcon(pm)



def protein_thumbnail(path, size: int = 56) -> QIcon:
    """Return a cached mini structure thumbnail derived from real C-alpha coordinates."""
    from pathlib import Path
    p = Path(path)
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        mtime = -1
    return _protein_thumbnail_cached(str(p), mtime, int(size))


@lru_cache(maxsize=384)
def _protein_thumbnail_cached(path_string: str, mtime_ns: int, size: int) -> QIcon:
    """Create one thumbnail per file version/size, avoiding repeated structure parsing on every toolbox open."""
    from pathlib import Path
    try:
        import gemmi
        import numpy as np
        st = gemmi.read_structure(str(Path(path_string)))
        coords = []
        if len(st):
            for chain in st[0]:
                for residue in chain:
                    ca = next((a for a in residue if a.name.strip().upper() == "CA"), None)
                    if ca is not None:
                        coords.append([float(ca.pos.x), float(ca.pos.y), float(ca.pos.z)])
        if len(coords) < 3 and len(st):
            coords = [[float(a.pos.x), float(a.pos.y), float(a.pos.z)] for c in st[0] for r in c for a in r]
        if len(coords) < 2:
            return make_icon("protein", size)
        arr = np.asarray(coords, dtype=float)
        arr -= arr.mean(axis=0)
        _u, _s, vt = np.linalg.svd(arr, full_matrices=False)
        xy = arr @ vt[:2].T
        span = np.ptp(xy, axis=0); span[span < 1e-8] = 1.0
        xy = (xy - xy.min(axis=0)) / span

        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        qp = QPainter(pm); qp.setRenderHint(QPainter.Antialiasing, True)
        qp.setPen(Qt.NoPen); qp.setBrush(QColor("#f4f7fa")); qp.drawRoundedRect(QRectF(1,1,size-2,size-2), 7, 7)
        pen = _pen(QColor("#4d6f98"), max(1.8, size/22)); qp.setPen(pen); qp.setBrush(Qt.NoBrush)
        margin = size * .16
        pts = [QPointF(margin + float(x)*(size-2*margin), margin + (1-float(y))*(size-2*margin)) for x,y in xy]
        pathp = QPainterPath(pts[0])
        for pt in pts[1:]: pathp.lineTo(pt)
        qp.drawPath(pathp)
        qp.setPen(Qt.NoPen); qp.setBrush(QColor("#7b5cb7"))
        for pt in pts[::max(1, len(pts)//9)]: qp.drawEllipse(pt, max(1.8,size*.035), max(1.8,size*.035))
        qp.end()
        return QIcon(pm)
    except Exception:
        return make_icon("protein", size)
