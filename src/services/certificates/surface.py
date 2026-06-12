"""Superfície de desenho abstrata dos diplomas.

Contrato mínimo de primitivas (retângulo, linha, círculo, polígono, path,
texto, imagem) com origem no canto inferior-esquerdo e y para cima (convenção
ReportLab). O mesmo código de ``shapes``/``renderer`` serve ao PDF
(``ReportLabSurface``) e, na Fase 5, ao preview (``TkSurface``) — só muda o
backend. Cores são strings hex ("#RRGGBB"); ``None`` = não pintar/contornar.

Nota ReportLab: ``setFillColor``/``setStrokeColor`` REDEFINEM o alpha. Por isso
o ``ReportLabSurface`` guarda o alpha corrente e o reaplica após cada cor.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

# Segmento de path: ("m",x,y) mover · ("l",x,y) linha · ("c",x1,y1,x2,y2,x3,y3)
# curva de Bézier cúbica · ("z",) fechar.
PathSeg = tuple


class DrawingSurface:
    """Interface comum. Backends concretos implementam os métodos de desenho."""

    width: float = 0.0
    height: float = 0.0

    def rect(self, x: float, y: float, w: float, h: float, *, fill: str | None = None,
             stroke: str | None = None, line_width: float = 1.0, radius: float = 0.0,
             dash: Sequence[float] | None = None) -> None:
        raise NotImplementedError

    def line(self, x1: float, y1: float, x2: float, y2: float, *, stroke: str,
             line_width: float = 1.0, dash: Sequence[float] | None = None) -> None:
        raise NotImplementedError

    def circle(self, cx: float, cy: float, r: float, *, fill: str | None = None,
               stroke: str | None = None, line_width: float = 1.0,
               dash: Sequence[float] | None = None) -> None:
        raise NotImplementedError

    def polygon(self, points: Sequence[tuple[float, float]], *, fill: str | None = None,
                stroke: str | None = None, line_width: float = 1.0) -> None:
        raise NotImplementedError

    def path(self, segments: Sequence[PathSeg], *, fill: str | None = None,
             stroke: str | None = None, line_width: float = 1.0) -> None:
        raise NotImplementedError

    def text(self, x: float, y: float, s: str, *, font: str, size: float, fill: str,
             anchor: str = "start", char_space: float = 0.0) -> None:
        raise NotImplementedError

    def image(self, source: Any, x: float, y: float, w: float, h: float, *,
              opacity: float = 1.0) -> None:
        raise NotImplementedError

    @contextmanager
    def alpha(self, value: float) -> Iterator[None]:
        """Opacidade temporária (marca d'água). Backend sobrescreve se suportar."""
        yield


class ReportLabSurface(DrawingSurface):
    """Backend de PDF: desenha no ``canvas`` do ReportLab."""

    def __init__(self, canvas: Any, width: float, height: float) -> None:
        from reportlab.lib import colors

        self._c = canvas
        self._colors = colors
        self.width = width
        self.height = height
        self._alpha = 1.0  # alpha corrente, reaplicado após cada set*Color

    def _hex(self, value: str) -> Any:
        return self._colors.HexColor(value)

    def _set_fill(self, color: str) -> None:
        self._c.setFillColor(self._hex(color))
        self._c.setFillAlpha(self._alpha)

    def _set_stroke(self, color: str) -> None:
        self._c.setStrokeColor(self._hex(color))
        self._c.setStrokeAlpha(self._alpha)

    def rect(self, x, y, w, h, *, fill=None, stroke=None, line_width=1.0, radius=0.0, dash=None):
        c = self._c
        c.saveState()
        if dash:
            c.setDash(list(dash))
        c.setLineWidth(line_width)
        if stroke is not None:
            self._set_stroke(stroke)
        if fill is not None:
            self._set_fill(fill)
        if radius and radius > 0:
            c.roundRect(x, y, w, h, radius, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)
        else:
            c.rect(x, y, w, h, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)
        c.restoreState()

    def line(self, x1, y1, x2, y2, *, stroke, line_width=1.0, dash=None):
        c = self._c
        c.saveState()
        if dash:
            c.setDash(list(dash))
        c.setLineWidth(line_width)
        self._set_stroke(stroke)
        c.line(x1, y1, x2, y2)
        c.restoreState()

    def circle(self, cx, cy, r, *, fill=None, stroke=None, line_width=1.0, dash=None):
        c = self._c
        c.saveState()
        if dash:
            c.setDash(list(dash))
        c.setLineWidth(line_width)
        if stroke is not None:
            self._set_stroke(stroke)
        if fill is not None:
            self._set_fill(fill)
        c.circle(cx, cy, r, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)
        c.restoreState()

    def polygon(self, points, *, fill=None, stroke=None, line_width=1.0):
        c = self._c
        path = c.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for px, py in points[1:]:
            path.lineTo(px, py)
        path.close()
        c.saveState()
        c.setLineWidth(line_width)
        if stroke is not None:
            self._set_stroke(stroke)
        if fill is not None:
            self._set_fill(fill)
        c.drawPath(path, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)
        c.restoreState()

    def path(self, segments, *, fill=None, stroke=None, line_width=1.0):
        c = self._c
        p = c.beginPath()
        for seg in segments:
            op = seg[0]
            if op == "m":
                p.moveTo(seg[1], seg[2])
            elif op == "l":
                p.lineTo(seg[1], seg[2])
            elif op == "c":
                p.curveTo(seg[1], seg[2], seg[3], seg[4], seg[5], seg[6])
            elif op == "z":
                p.close()
        c.saveState()
        c.setLineWidth(line_width)
        if stroke is not None:
            self._set_stroke(stroke)
        if fill is not None:
            self._set_fill(fill)
        c.drawPath(p, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)
        c.restoreState()

    def text(self, x, y, s, *, font, size, fill, anchor="start", char_space=0.0):
        c = self._c
        c.saveState()
        c.setFont(font, size)
        self._set_fill(fill)
        if char_space and len(s) > 1:
            widths = [c.stringWidth(ch, font, size) for ch in s]
            total = sum(widths) + char_space * (len(s) - 1)
            if anchor == "middle":
                cursor = x - total / 2.0
            elif anchor == "end":
                cursor = x - total
            else:
                cursor = x
            for ch, ch_w in zip(s, widths):
                c.drawString(cursor, y, ch)
                cursor += ch_w + char_space
        elif anchor == "middle":
            c.drawCentredString(x, y, s)
        elif anchor == "end":
            c.drawRightString(x, y, s)
        else:
            c.drawString(x, y, s)
        c.restoreState()

    def image(self, source, x, y, w, h, *, opacity=1.0):
        c = self._c
        c.saveState()
        if opacity < 1.0:
            c.setFillAlpha(opacity)
            c.setStrokeAlpha(opacity)
        c.drawImage(source, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")
        c.restoreState()

    @contextmanager
    def alpha(self, value):
        previous = self._alpha
        self._alpha = value
        try:
            yield
        finally:
            self._alpha = previous
