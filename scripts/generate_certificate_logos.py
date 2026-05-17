from __future__ import annotations

import struct
import zlib
from pathlib import Path

SIZE = 1024
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "certificates" / "logos"

Color = tuple[int, int, int]


def _clamp(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
    png.extend(_chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
    png.extend(_chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(png))


class Canvas:
    def __init__(self, size: int = SIZE) -> None:
        self.width = size
        self.height = size
        self.pixels = bytearray(size * size * 4)

    def blend_pixel(self, x: int, y: int, color: Color, alpha: float = 1.0) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height or alpha <= 0:
            return
        index = (y * self.width + x) * 4
        source_alpha = min(alpha, 1.0)
        target_alpha = self.pixels[index + 3] / 255
        out_alpha = source_alpha + target_alpha * (1 - source_alpha)
        if out_alpha <= 0:
            return
        for channel in range(3):
            target = self.pixels[index + channel] / 255
            source = color[channel] / 255
            out = (source * source_alpha + target * target_alpha * (1 - source_alpha)) / out_alpha
            self.pixels[index + channel] = _clamp(out * 255)
        self.pixels[index + 3] = _clamp(out_alpha * 255)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color, alpha: float = 1.0) -> None:
        left, right = sorted((max(0, x0), min(self.width - 1, x1)))
        top, bottom = sorted((max(0, y0), min(self.height - 1, y1)))
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                self.blend_pixel(x, y, color, alpha)

    def circle(self, cx: int, cy: int, radius: int, color: Color, alpha: float = 1.0) -> None:
        radius_sq = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                distance_sq = (x - cx) ** 2 + (y - cy) ** 2
                if distance_sq <= radius_sq:
                    self.blend_pixel(x, y, color, alpha)

    def ring(self, cx: int, cy: int, outer: int, inner: int, color: Color, alpha: float = 1.0) -> None:
        outer_sq = outer * outer
        inner_sq = inner * inner
        for y in range(cy - outer, cy + outer + 1):
            for x in range(cx - outer, cx + outer + 1):
                distance_sq = (x - cx) ** 2 + (y - cy) ** 2
                if inner_sq <= distance_sq <= outer_sq:
                    self.blend_pixel(x, y, color, alpha)

    def line(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: Color,
        alpha: float = 1.0,
        thickness: int = 1,
    ) -> None:
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        radius = max(0, thickness // 2)
        for step in range(steps + 1):
            t = step / steps
            x = round(x0 + (x1 - x0) * t)
            y = round(y0 + (y1 - y0) * t)
            self.rect(x - radius, y - radius, x + radius, y + radius, color, alpha)

    def polygon(self, points: list[tuple[int, int]], color: Color, alpha: float = 1.0) -> None:
        min_x = max(0, min(x for x, _y in points))
        max_x = min(self.width - 1, max(x for x, _y in points))
        min_y = max(0, min(y for _x, y in points))
        max_y = min(self.height - 1, max(y for _x, y in points))
        for y in range(min_y, max_y + 1):
            intersections = []
            for index, point in enumerate(points):
                x1, y1 = point
                x2, y2 = points[(index + 1) % len(points)]
                if (y1 <= y < y2) or (y2 <= y < y1):
                    x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                    intersections.append(int(round(x)))
            intersections.sort()
            for start, end in zip(intersections[0::2], intersections[1::2]):
                self.rect(max(min_x, start), y, min(max_x, end), y, color, alpha)

    def checker_disc(
        self,
        cx: int,
        cy: int,
        radius: int,
        square: int,
        color_a: Color,
        color_b: Color,
        alpha: float = 1.0,
    ) -> None:
        radius_sq = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius_sq:
                    color = color_a if ((x - cx) // square + (y - cy) // square) % 2 == 0 else color_b
                    self.blend_pixel(x, y, color, alpha)

    def save(self, path: Path) -> None:
        write_png(path, self.width, self.height, self.pixels)


def draw_rook(canvas: Canvas, cx: int, cy: int, scale: float, color: Color) -> None:
    s = scale
    canvas.rect(cx - int(140 * s), cy - int(220 * s), cx + int(140 * s), cy - int(154 * s), color)
    for offset in (-105, 0, 105):
        canvas.rect(cx + int((offset - 34) * s), cy - int(300 * s), cx + int((offset + 34) * s), cy - int(174 * s), color)
    canvas.rect(cx - int(105 * s), cy - int(145 * s), cx + int(105 * s), cy + int(140 * s), color)
    canvas.rect(cx - int(185 * s), cy + int(132 * s), cx + int(185 * s), cy + int(208 * s), color)


def draw_pawn(canvas: Canvas, cx: int, cy: int, scale: float, color: Color) -> None:
    s = scale
    canvas.circle(cx, cy - int(180 * s), int(74 * s), color)
    canvas.circle(cx, cy - int(72 * s), int(112 * s), color)
    canvas.rect(cx - int(142 * s), cy + int(45 * s), cx + int(142 * s), cy + int(120 * s), color)
    canvas.rect(cx - int(200 * s), cy + int(120 * s), cx + int(200 * s), cy + int(190 * s), color)


def draw_queen(canvas: Canvas, cx: int, cy: int, scale: float, color: Color) -> None:
    s = scale
    crown = [(-140, -250), (-70, -310), (0, -245), (70, -310), (140, -250), (95, -95), (-95, -95)]
    canvas.polygon([(cx + int(x * s), cy + int(y * s)) for x, y in crown], color)
    for offset in (-140, -70, 0, 70, 140):
        canvas.circle(cx + int(offset * s), cy - int(312 * s), int(34 * s), color)
    canvas.circle(cx, cy - int(68 * s), int(118 * s), color)
    canvas.rect(cx - int(128 * s), cy + int(45 * s), cx + int(128 * s), cy + int(130 * s), color)
    canvas.rect(cx - int(195 * s), cy + int(125 * s), cx + int(195 * s), cy + int(190 * s), color)


def draw_knight(canvas: Canvas, cx: int, cy: int, scale: float, color: Color) -> None:
    s = scale
    points = [
        (-145, 210),
        (175, 210),
        (125, 115),
        (75, 20),
        (132, -65),
        (52, -242),
        (-105, -295),
        (-185, -205),
        (-110, -130),
        (-220, -20),
        (-115, 55),
        (-88, 125),
    ]
    canvas.polygon([(cx + int(x * s), cy + int(y * s)) for x, y in points], color)
    canvas.circle(cx + int(56 * s), cy - int(142 * s), int(18 * s), (255, 255, 255))
    canvas.rect(cx - int(205 * s), cy + int(204 * s), cx + int(215 * s), cy + int(280 * s), color)


def draw_trophy(canvas: Canvas, cx: int, cy: int, scale: float, color: Color) -> None:
    s = scale
    cup = [(-150, -250), (150, -250), (110, -55), (55, 8), (-55, 8), (-110, -55)]
    canvas.polygon([(cx + int(x * s), cy + int(y * s)) for x, y in cup], color)
    canvas.ring(cx - int(155 * s), cy - int(145 * s), int(92 * s), int(54 * s), color)
    canvas.ring(cx + int(155 * s), cy - int(145 * s), int(92 * s), int(54 * s), color)
    canvas.rect(cx - int(45 * s), cy + int(4 * s), cx + int(45 * s), cy + int(130 * s), color)
    canvas.rect(cx - int(155 * s), cy + int(130 * s), cx + int(155 * s), cy + int(205 * s), color)


def logo_albericus_knight() -> Canvas:
    canvas = Canvas()
    blue = (30, 58, 138)
    gold = (200, 162, 74)
    canvas.checker_disc(512, 512, 404, 96, (239, 246, 255), (219, 234, 254))
    canvas.ring(512, 512, 450, 388, blue)
    canvas.ring(512, 512, 382, 360, gold)
    draw_knight(canvas, 522, 500, 1.12, blue)
    canvas.circle(512, 512, 486, gold, 0.12)
    return canvas


def logo_clube_rook() -> Canvas:
    canvas = Canvas()
    navy = (15, 23, 42)
    gold = (184, 134, 11)
    shield = [(512, 70), (835, 192), (780, 690), (512, 948), (244, 690), (189, 192)]
    canvas.polygon(shield, navy)
    inner = [(512, 138), (765, 232), (720, 660), (512, 858), (304, 660), (259, 232)]
    canvas.polygon(inner, (248, 250, 252))
    canvas.ring(512, 510, 260, 230, gold)
    draw_rook(canvas, 512, 526, 0.82, navy)
    return canvas


def logo_escola_pawn() -> Canvas:
    canvas = Canvas()
    teal = (15, 118, 110)
    orange = (245, 158, 11)
    canvas.circle(512, 512, 430, (240, 253, 250))
    canvas.ring(512, 512, 448, 408, teal)
    canvas.polygon([(190, 650), (468, 560), (468, 760), (190, 835)], orange)
    canvas.polygon([(834, 650), (556, 560), (556, 760), (834, 835)], orange)
    canvas.line(512, 552, 512, 820, teal, 1.0, 18)
    draw_pawn(canvas, 512, 420, 0.76, teal)
    return canvas


def logo_torneio_trophy() -> Canvas:
    canvas = Canvas()
    slate = (51, 65, 85)
    gold = (217, 164, 65)
    canvas.checker_disc(512, 512, 420, 112, (241, 245, 249), (226, 232, 240))
    canvas.ring(512, 512, 450, 408, slate)
    draw_trophy(canvas, 512, 520, 1.02, gold)
    draw_pawn(canvas, 512, 345, 0.30, slate)
    return canvas


def logo_selo_queen() -> Canvas:
    canvas = Canvas()
    slate = (51, 65, 85)
    silver = (148, 163, 184)
    canvas.circle(512, 512, 430, (248, 250, 252))
    canvas.ring(512, 512, 454, 404, silver)
    canvas.ring(512, 512, 382, 360, slate)
    draw_queen(canvas, 512, 522, 0.86, slate)
    return canvas


def main() -> None:
    logos = {
        "albericus_knight.png": logo_albericus_knight(),
        "clube_rook.png": logo_clube_rook(),
        "escola_pawn.png": logo_escola_pawn(),
        "torneio_trophy.png": logo_torneio_trophy(),
        "selo_queen.png": logo_selo_queen(),
    }
    for filename, canvas in logos.items():
        path = OUTPUT_DIR / filename
        canvas.save(path)
        print(path)


if __name__ == "__main__":
    main()
