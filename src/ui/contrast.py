"""Contraste WCAG — aritmética pura de cor (B-2 / P2-11).

Sem Tk, sem tema: entra cor, sai número. Quem sabe *quais* cores se encontram na
tela é [theme_audit.py](theme_audit.py); este módulo só sabe medir.

Fórmulas da WCAG 2.1 (§1.4.3 e §1.4.11). Os limites:

======  =======  ====================================================
 4.5:1  ``AA``   texto normal
 3.0:1  ``AA``   texto grande (≥18pt, ou ≥14pt em negrito)
 3.0:1  ``AA``   componente de interface e borda que carrega significado
======  =======  ====================================================

Um detalhe que engana: contraste **não** é diferença de brilho percebido, é
razão entre luminâncias *linearizadas*. Duas cores que "parecem" distantes
podem reprovar — por isso a conta, e não o olho, decide o que entra no tema.
"""
from __future__ import annotations

from dataclasses import dataclass

# Limites da WCAG 2.1 nível AA.
AA_NORMAL_TEXT = 4.5
AA_LARGE_TEXT = 3.0
AA_UI_COMPONENT = 3.0


# Tintas disponíveis para texto sobre preenchimento colorido. Duas, e não uma:
# é a escolha entre elas que faz um botão âmbar ganhar texto escuro e um botão
# azul ganhar texto claro, sem ninguém decidir cor a cor.
INK_LIGHT = "#FFFFFF"
INK_DARK = "#0B0F19"


def parse_hex(color: str) -> tuple[int, int, int]:
    """``#RRGGBB`` (ou ``#RGB``) para (r, g, b) em 0–255."""
    raw = str(color).strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raise ValueError(f"Cor hexadecimal invalida: {color!r}")
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError as exc:
        raise ValueError(f"Cor hexadecimal invalida: {color!r}") from exc


def relative_luminance(color: str) -> float:
    """Luminância relativa (0 = preto, 1 = branco), WCAG 2.1 §Relative luminance.

    Cada canal é linearizado antes da soma ponderada: é essa linearização que
    faz um cinza médio pesar bem menos do que a intuição sugere.
    """
    canais = []
    for valor in parse_hex(color):
        c = valor / 255
        canais.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canais
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first: str, second: str) -> float:
    """Razão de contraste entre duas cores, de 1.0 (iguais) a 21.0 (preto/branco)."""
    a, b = relative_luminance(first), relative_luminance(second)
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


def best_ink(fill: str, light: str = INK_LIGHT, dark: str = INK_DARK) -> str:
    """A tinta mais legível sobre ``fill`` — calculada, não escolhida à mão.

    Existe porque o accent é do usuário: são 15 presets em duas faces, e alguém
    ter de lembrar que sobre amarelo o texto é escuro e sobre índigo é claro
    seria uma regra que envelhece na primeira cor nova. Empate vai para a tinta
    clara, que é a convenção de botão preenchido.
    """
    return light if contrast_ratio(light, fill) >= contrast_ratio(dark, fill) else dark


def mix_hex(base: str, other: str, amount: float) -> str:
    """Mistura linear de duas cores: ``amount=0`` devolve ``base``, ``1`` devolve ``other``.

    É o tijolo das cores *derivadas* (F5.1): o fundo e a borda de um campo não
    são escolhidos numa tabela, são calculados a partir do painel em que o campo
    vive — assim um preset de painel novo já nasce com campos coerentes.
    """
    t = min(1.0, max(0.0, float(amount)))
    canais = (
        round(a + (b - a) * t)
        for a, b in zip(parse_hex(base), parse_hex(other))
    )
    return "#{:02X}{:02X}{:02X}".format(*canais)


# Famílias de par. Servem para cobrar níveis diferentes de cada uma: o tema de
# alto contraste manda nas SUPERFÍCIES (fundo, painel, texto), mas o vermelho de
# perigo e o âmbar de aviso são semânticos e valem para todos os temas — exigir
# AAA deles seria pedir que "alto contraste" redefinisse o que é perigo.
SURFACE = "superficie"
FILL = "preenchimento"
TABLE = "tabela"
COMPONENT = "componente"


@dataclass(frozen=True)
class ContrastPair:
    """Um encontro de cores que a tela realmente produz.

    ``role`` é a descrição do encontro ("texto principal sobre painel"), e é o
    que aparece no relatório — um par reprovado sem nome vira uma linha que
    ninguém sabe onde consertar.
    """

    role: str
    foreground: str
    background: str
    minimum: float = AA_NORMAL_TEXT
    kind: str = SURFACE

    @property
    def ratio(self) -> float:
        return contrast_ratio(self.foreground, self.background)

    @property
    def passes(self) -> bool:
        # Arredonda para duas casas antes de comparar: 4.4999 exibido como
        # "4.50" e reprovado seria um relatorio que se contradiz na tela.
        return round(self.ratio, 2) >= self.minimum

    def describe(self) -> str:
        return (
            f"{self.role}: {self.foreground} sobre {self.background} = "
            f"{self.ratio:.2f}:1 (mínimo {self.minimum}:1)"
        )


def failures(pairs: list[ContrastPair]) -> list[ContrastPair]:
    """Só os pares que reprovam, na ordem do pior para o melhor."""
    return sorted((p for p in pairs if not p.passes), key=lambda p: p.ratio)
