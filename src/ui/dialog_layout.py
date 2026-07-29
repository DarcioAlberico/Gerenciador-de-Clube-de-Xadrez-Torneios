"""Tamanho e posição de janela modal — a conta, sem abrir janela (F5.8).

Camada pura do diálogo canônico. O que ela decide é uma pergunta só: **cabe na
tela?** — e essa pergunta o customtkinter não faz. Ele escala a geometria que
recebe (``CTkToplevel.geometry`` multiplica pelo *window scaling*) e entrega o
resultado ao Tk sem olhar para o monitor.

Por isso os 22 ``geometry()`` fixos do P3-10 são um problema real e não teórico:
o app nasce em **120%** e o usuário pode ir a 160%. Um diálogo escrito como
``geometry("900x700")`` vira 1440×1120 nesse ajuste — maior que a tela inteira
de um notebook de 1366×768. O rodapé, onde ficam Salvar e Cancelar, é a parte
que sai para fora; a janela não tem barra de rolagem e o Tk não deixa arrastar
para além do topo. O diálogo simplesmente não tem saída.

A regra aqui é: reduzir o pedido **antes** da escala, de modo que o resultado
escalado ainda caiba com uma margem de respiro.
"""
from __future__ import annotations

Size = tuple[int, int]

# Fração da tela que um modal pode ocupar. 92% deixa a barra de tarefas e as
# bordas da janela visíveis — modal colado nas quatro bordas passa a impressão
# de que o app travou em tela cheia.
SCREEN_MARGIN = 0.92

# Piso de legibilidade: abaixo disso o modal não tem o que mostrar, e é melhor
# ele vazar um pouco do que virar uma faixa inútil.
MIN_SIZE: Size = (320, 240)


def fitted_size(base: Size, *, scale: float, screen: Size, margin: float = SCREEN_MARGIN) -> Size:
    """Tamanho a **pedir** ao Tk para que, já escalado, caiba na tela.

    ``base`` é a geometria pensada a 100%; ``scale`` é o fator em vigor (1.2
    para os 120% padrão). Como o customtkinter multiplica o que recebe, o teto
    é dividido pela escala — pedir menos é o único jeito de o resultado caber.
    """
    escala = scale if scale > 0 else 1.0
    teto_w = max(MIN_SIZE[0], int(screen[0] * margin / escala))
    teto_h = max(MIN_SIZE[1], int(screen[1] * margin / escala))
    return min(base[0], teto_w), min(base[1], teto_h)


def centered_position(size: Size, *, owner: tuple[int, int, int, int], screen: Size) -> Size:
    """Canto superior esquerdo para centralizar ``size`` sobre ``owner``.

    ``owner`` é ``(x, y, largura, altura)`` da janela de origem, em pixels de
    tela (já escalados). O resultado é preso à tela: modal centralizado sobre
    uma janela encostada na borda ficaria metade para fora, e a metade que sai
    é sempre a de baixo — de novo, a dos botões.

    A altura usa **um terço** da sobra, não a metade: modal centralizado na
    vertical exata parece baixo demais, e o olho procura diálogo acima do
    centro óptico.
    """
    ox, oy, ow, oh = owner
    x = ox + max((ow - size[0]) // 2, 0)
    y = oy + max((oh - size[1]) // 3, 0)
    x = max(0, min(x, screen[0] - size[0]))
    y = max(0, min(y, screen[1] - size[1]))
    return x, y


def geometry_string(size: Size, position: Size | None = None) -> str:
    """``"LxA"`` ou ``"LxA+X+Y"`` — o formato que o Tk espera."""
    largura, altura = size
    if position is None:
        return f"{largura}x{altura}"
    return f"{largura}x{altura}+{position[0]}+{position[1]}"
