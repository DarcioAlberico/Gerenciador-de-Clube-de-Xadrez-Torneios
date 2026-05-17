from __future__ import annotations

import struct
import zlib
from pathlib import Path

WIDTH = 1920
HEIGHT = 1358
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "certificates" / "backgrounds"

Color = tuple[int, int, int]


def _clamp(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    png.extend(_chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
    png.extend(_chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(png))


class Canvas:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT, background: Color = (255, 255, 255)) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(background * width * height)

    def blend_pixel(self, x: int, y: int, color: Color, alpha: float = 1.0) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height or alpha <= 0:
            return
        index = (y * self.width + x) * 3
        inv = 1.0 - min(alpha, 1.0)
        self.pixels[index] = _clamp(self.pixels[index] * inv + color[0] * alpha)
        self.pixels[index + 1] = _clamp(self.pixels[index + 1] * inv + color[1] * alpha)
        self.pixels[index + 2] = _clamp(self.pixels[index + 2] * inv + color[2] * alpha)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color, alpha: float = 1.0) -> None:
        left, right = sorted((max(0, x0), min(self.width - 1, x1)))
        top, bottom = sorted((max(0, y0), min(self.height - 1, y1)))
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
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

    def circle(self, cx: int, cy: int, radius: int, color: Color, alpha: float = 1.0) -> None:
        r2 = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                    self.blend_pixel(x, y, color, alpha)

    def outline(self, margin: int, color: Color, alpha: float = 1.0, thickness: int = 4) -> None:
        self.line(margin, margin, self.width - margin, margin, color, alpha, thickness)
        self.line(margin, self.height - margin, self.width - margin, self.height - margin, color, alpha, thickness)
        self.line(margin, margin, margin, self.height - margin, color, alpha, thickness)
        self.line(self.width - margin, margin, self.width - margin, self.height - margin, color, alpha, thickness)

    def save(self, path: Path) -> None:
        write_png(path, self.width, self.height, self.pixels)


def draw_pawn(canvas: Canvas, cx: int, cy: int, scale: float, color: Color, alpha: float) -> None:
    s = scale
    canvas.circle(cx, cy - int(105 * s), int(45 * s), color, alpha)
    canvas.circle(cx, cy - int(34 * s), int(70 * s), color, alpha)
    canvas.rect(cx - int(92 * s), cy + int(30 * s), cx + int(92 * s), cy + int(76 * s), color, alpha)
    canvas.rect(cx - int(130 * s), cy + int(78 * s), cx + int(130 * s), cy + int(118 * s), color, alpha)


def draw_rook(canvas: Canvas, cx: int, cy: int, scale: float, color: Color, alpha: float) -> None:
    s = scale
    canvas.rect(cx - int(92 * s), cy - int(125 * s), cx + int(92 * s), cy - int(86 * s), color, alpha)
    for offset in (-70, 0, 70):
        canvas.rect(cx + int((offset - 21) * s), cy - int(165 * s), cx + int((offset + 21) * s), cy - int(92 * s), color, alpha)
    canvas.rect(cx - int(72 * s), cy - int(82 * s), cx + int(72 * s), cy + int(80 * s), color, alpha)
    canvas.rect(cx - int(120 * s), cy + int(80 * s), cx + int(120 * s), cy + int(125 * s), color, alpha)


def draw_queen(canvas: Canvas, cx: int, cy: int, scale: float, color: Color, alpha: float) -> None:
    s = scale
    for offset in (-95, -45, 0, 45, 95):
        canvas.circle(cx + int(offset * s), cy - int(142 * s), int(24 * s), color, alpha)
        canvas.line(cx, cy - int(50 * s), cx + int(offset * s), cy - int(128 * s), color, alpha, int(24 * s))
    canvas.circle(cx, cy - int(30 * s), int(78 * s), color, alpha)
    canvas.rect(cx - int(82 * s), cy + int(42 * s), cx + int(82 * s), cy + int(90 * s), color, alpha)
    canvas.rect(cx - int(125 * s), cy + int(92 * s), cx + int(125 * s), cy + int(128 * s), color, alpha)


def checker(canvas: Canvas, square: int, color_a: Color, color_b: Color, alpha: float, offset_x: int = 0, offset_y: int = 0) -> None:
    for y in range(offset_y, canvas.height, square):
        for x in range(offset_x, canvas.width, square):
            color = color_a if ((x - offset_x) // square + (y - offset_y) // square) % 2 == 0 else color_b
            canvas.rect(x, y, x + square - 1, y + square - 1, color, alpha)


def diagonal_lines(canvas: Canvas, spacing: int, color: Color, alpha: float, thickness: int = 2) -> None:
    for start in range(-canvas.height, canvas.width, spacing):
        canvas.line(start, canvas.height, start + canvas.height, 0, color, alpha, thickness)


def background_tabuleiro_sutil() -> Canvas:
    canvas = Canvas(background=(250, 252, 255))
    checker(canvas, 160, (210, 226, 246), (255, 255, 255), 0.58, 0, 0)
    canvas.rect(430, 235, 1490, 1123, (255, 255, 255), 0.74)
    canvas.outline(78, (30, 64, 128), 0.44, 5)
    canvas.outline(112, (147, 197, 253), 0.34, 2)
    return canvas


def background_xadrez_classico() -> Canvas:
    canvas = Canvas(background=(252, 249, 240))
    checker(canvas, 132, (233, 220, 194), (252, 249, 240), 0.62)
    canvas.rect(250, 190, 1670, 1168, (255, 255, 255), 0.72)
    canvas.outline(70, (80, 56, 31), 0.52, 5)
    canvas.outline(105, (200, 162, 74), 0.38, 3)
    draw_pawn(canvas, 240, 1010, 1.05, (80, 56, 31), 0.40)
    draw_rook(canvas, 1665, 330, 0.9, (80, 56, 31), 0.34)
    diagonal_lines(canvas, 72, (200, 162, 74), 0.09, 2)
    return canvas


def background_xadrez_escolar() -> Canvas:
    canvas = Canvas(background=(247, 253, 250))
    checker(canvas, 150, (204, 251, 241), (254, 249, 195), 0.52)
    canvas.rect(310, 200, 1610, 1158, (255, 255, 255), 0.74)
    canvas.outline(76, (15, 118, 110), 0.46, 5)
    for index, (cx, cy, color) in enumerate(
        [
            (230, 290, (245, 158, 11)),
            (1680, 1040, (15, 118, 110)),
            (400, 1120, (59, 130, 246)),
            (1540, 240, (245, 158, 11)),
        ]
    ):
        draw_pawn(canvas, cx, cy, 0.55 + index * 0.04, color, 0.34)
    return canvas


def background_xadrez_premium() -> Canvas:
    canvas = Canvas(background=(10, 18, 32))
    checker(canvas, 160, (17, 34, 64), (10, 18, 32), 0.88)
    for radius, alpha in ((660, 0.22), (460, 0.20), (260, 0.18)):
        canvas.circle(WIDTH // 2, HEIGHT // 2, radius, (42, 74, 110), alpha)
    canvas.rect(260, 190, 1660, 1168, (248, 250, 252), 0.78)
    canvas.outline(70, (184, 134, 11), 0.78, 6)
    canvas.outline(112, (226, 196, 106), 0.50, 3)
    draw_queen(canvas, 1565, 1000, 0.82, (184, 134, 11), 0.36)
    draw_rook(canvas, 350, 330, 0.74, (226, 196, 106), 0.24)
    return canvas


def background_pecas_marca_dagua() -> Canvas:
    canvas = Canvas(background=(255, 255, 255))
    checker(canvas, 180, (226, 232, 240), (255, 255, 255), 0.34)
    canvas.rect(350, 225, 1570, 1133, (255, 255, 255), 0.80)
    canvas.outline(84, (100, 116, 139), 0.42, 4)
    draw_queen(canvas, 510, 1010, 1.45, (51, 65, 85), 0.16)
    draw_rook(canvas, 1460, 390, 1.35, (51, 65, 85), 0.14)
    draw_pawn(canvas, 960, 240, 0.88, (51, 65, 85), 0.12)
    return canvas


def main() -> None:
    backgrounds = {
        "tabuleiro_sutil.png": background_tabuleiro_sutil(),
        "xadrez_classico.png": background_xadrez_classico(),
        "xadrez_escolar.png": background_xadrez_escolar(),
        "xadrez_premium.png": background_xadrez_premium(),
        "pecas_marca_dagua.png": background_pecas_marca_dagua(),
    }
    for filename, canvas in backgrounds.items():
        path = OUTPUT_DIR / filename
        canvas.save(path)
        print(path)


if __name__ == "__main__":
    main()
