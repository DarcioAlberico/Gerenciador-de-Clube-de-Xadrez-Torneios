"""Factories de campo de entrada — anatomia única (F5.2 / ESPEC_UI_UX §4.6).

O que as factories fecham, e que solto em cada tela virava variação (P3-3/5/6):

- **altura única de 36px** (``FIELD_HEIGHT``, a mesma dos botões): campo e botão
  alinham na mesma linha — antes o campo nascia com 28px ao lado de botões de 36;
- **escala fechada de larguras**: ``FIELD_SM`` (números/datas), ``FIELD_MD``
  (padrão), ``FIELD_LG`` (nomes/caminhos) — no lugar das 67 larguras distintas;
  para ocupar a coluna toda, posicione com ``sticky="ew"`` (o ``width`` vira
  mínimo, não use larguras fora da escala para isso);
- **placeholder obrigatório** em campo de texto: a caixa vazia sem dica era a
  regra (94 de 150 campos);
- **raio e fonte únicos** (``FIELD_RADIUS``, ``font_field``).

As CORES não são passadas aqui de propósito (exceto no ``select_field``): desde a
F5.1 elas vêm dos padrões do ``ThemeManager`` patchados pelos presets, e é isso
que deixa o ``restyle.py`` repintar os campos na troca de tema.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..theme import (
    SIZE_BODY,
    SPACE_XS,
    THEME_ACCENT,
    THEME_DANGER,
    THEME_FIELD_BG,
    THEME_FIELD_BORDER,
    THEME_FIELD_TEXT,
    THEME_PANEL_BG,
    THEME_TEXT_MAIN,
    THEME_TEXT_SUB,
    THEME_TREE_EVEN,
    THEME_WARNING_TEXT,
    font_field,
    font_field_label,
)

# Mesma altura de components/buttons.py (_DEFAULT_HEIGHT): e o alinhamento
# campo-botao na mesma linha que define a escala, nao um numero solto.
FIELD_HEIGHT = 36
FIELD_RADIUS = 6

# Escala fechada de larguras (ESPEC §4.6). FULL nao e uma largura: e grid com
# sticky="ew" — use FIELD_MD como minimo e deixe a coluna esticar.
FIELD_SM = 120
FIELD_MD = 240
FIELD_LG = 360


# ---------------------------------------------------------------------------
# Estados do campo (F5.3 / P3-4): repouso, foco, erro, aviso, desabilitado.
#
# Antes existiam TRES implementacoes locais de "pintar a borda de vermelho"
# (MaskedDateEntry, Config. do app, Config. do torneio), nenhuma com mensagem
# sob o campo; foco visivel nao existia (zero bindings de <FocusIn> no app) e
# campo desabilitado era indistinguivel do habilitado, porque o CTkEntry so
# esmaece o texto — nao tem `text_color_disabled` nem muda o fundo.
#
# A precedencia e uma so, e mora em _apply_field_state: erro > aviso > foco >
# repouso. Sem isso, focar um campo em erro apagaria o erro.
# ---------------------------------------------------------------------------
_STATE_ATTR = "_albericus_field_state"


def _field_state(widget: Any) -> dict[str, Any] | None:
    return getattr(widget, _STATE_ATTR, None)


def _apply_field_state(widget: Any) -> None:
    """Repinta o campo conforme o estado atual. Usa o ``configure`` original."""
    estado = _field_state(widget)
    if estado is None:
        return
    raw = estado["raw_configure"]
    if estado["disabled"]:
        # Sem fundo proprio o campo vira um contorno chapado sobre o painel:
        # some a afordancia de "da para digitar aqui", que e o ponto.
        visual = {"border_color": THEME_FIELD_BORDER, "fg_color": THEME_PANEL_BG, "border_width": 1}
    elif estado["error"]:
        visual = {"border_color": THEME_DANGER, "fg_color": THEME_FIELD_BG, "border_width": 2}
    elif estado["warning"]:
        visual = {"border_color": THEME_WARNING_TEXT, "fg_color": THEME_FIELD_BG, "border_width": 2}
    elif estado["focused"]:
        visual = {"border_color": THEME_ACCENT, "fg_color": THEME_FIELD_BG, "border_width": 2}
    else:
        visual = {"border_color": THEME_FIELD_BORDER, "fg_color": THEME_FIELD_BG, "border_width": 1}
    for opcao, valor in visual.items():
        try:
            raw(**{opcao: valor})
        except (ValueError, TypeError):
            continue  # opcao inexistente nesta classe (ex.: border_width no select)


def _update_hint(widget: Any) -> None:
    """Escreve a mensagem sob o campo, quando ``labeled_field`` reservou a linha."""
    estado = _field_state(widget)
    if estado is None or estado["hint"] is None:
        return
    if estado["error"]:
        texto, cor = estado["message"], THEME_DANGER
    elif estado["warning"]:
        texto, cor = estado["message"], THEME_WARNING_TEXT
    else:
        texto, cor = estado["help"], THEME_TEXT_SUB
    estado["hint"].configure(text=texto or "", text_color=cor)


def attach_field_states(widget: Any) -> Any:
    """Liga anel de foco e API de erro/aviso/desabilitado ao campo. Idempotente.

    O ``configure`` da instancia e embrulhado para que ``state="disabled"``
    vindo de qualquer lugar — inclusive das ~36 chamadas cruas que ainda
    existem nas telas — passe pela mesma pintura. Sem isso, "desabilitado
    distinto" so valeria para quem soubesse chamar o helper novo.
    """
    if _field_state(widget) is not None:
        return widget
    estado: dict[str, Any] = {
        "raw_configure": widget.configure,
        "error": False,
        "warning": False,
        "focused": False,
        "disabled": False,
        "message": "",
        "help": "",
        "hint": None,
    }
    setattr(widget, _STATE_ATTR, estado)

    def configure_wrapper(**kwargs: Any) -> Any:
        resultado = estado["raw_configure"](**kwargs)
        if "state" in kwargs:
            estado["disabled"] = str(kwargs["state"]) == "disabled"
            _apply_field_state(widget)
        return resultado

    widget.configure = configure_wrapper  # type: ignore[method-assign]

    def on_focus_in(_event: Any) -> None:
        estado["focused"] = True
        _apply_field_state(widget)

    def on_focus_out(_event: Any) -> None:
        estado["focused"] = False
        _apply_field_state(widget)

    # O bind vai no widget Tk de DENTRO: no CTkEntry o foco chega ao tk.Entry
    # interno, nao ao frame CTk (mesma pegadinha documentada na B-4). Num
    # select ou numa caixa de selecao nao ha `_entry`: quem recebe o foco e o
    # canvas, e e nele que o `_focusable` da F5.10 liga o `takefocus`.
    alvo = (
        getattr(widget, "_entry", None)
        or getattr(widget, "_textbox", None)
        or getattr(widget, "_canvas", None)
        or widget
    )
    try:
        alvo.bind("<FocusIn>", on_focus_in, add="+")
        alvo.bind("<FocusOut>", on_focus_out, add="+")
    except Exception:  # pragma: no cover - widget sem bind (nao deve acontecer)
        pass
    _apply_field_state(widget)
    return widget


# ---------------------------------------------------------------------------
# Teclado (F5.10 / P3-13)
#
# O achado do catalogo dizia "ordem de Tab = ordem de criacao". Medindo, o
# problema era outro e maior: **select e caixa de selecao nao entram na ordem
# de Tab de jeito nenhum**. O `tk_focusNext` visita `Entry` e `Text` e pula o
# resto — e no customtkinter TODO botao, select e checkbox e um frame com um
# canvas dentro, invisivel para a travessia.
#
# Consequencia pratica: um formulario de sete selects (a aba "Regras" da
# Config. do torneio) nao tinha um unico ponto de parada do teclado. Nao havia
# ordem errada; nao havia ordem.
#
# `takefocus=False` em botao secundario, que o catalogo pedia, **nao e
# necessario**: eles ja sao pulados. Foi verificado, nao suposto.
# ---------------------------------------------------------------------------
def _focusable(widget: Any) -> Any:
    """Coloca o widget na ordem de Tab e devolve o alvo Tk que recebe o foco."""
    canvas = getattr(widget, "_canvas", None)
    if canvas is None:
        return widget
    try:
        canvas.configure(takefocus=True)
    except Exception:  # pragma: no cover
        return widget
    return canvas


def _bind_keys(alvo: Any, mapa: dict[str, Callable[[Any], Any]]) -> None:
    for sequencia, acao in mapa.items():
        try:
            alvo.bind(sequencia, acao, add="+")
        except Exception:  # pragma: no cover
            continue


def keyboard_select(campo: Any) -> Any:
    """Torna um ``CTkOptionMenu`` operavel só com o teclado.

    ``Espaço``/``Enter``/``Alt+Baixo`` abrem a lista; ``↑``/``↓`` trocam o
    valor sem abrir, que é o gesto rápido de quem está preenchendo um
    formulário inteiro sem tirar a mão do teclado. Trocar o valor **dispara o
    ``command``** — senão o formulário mudaria na tela e não no estado.
    """
    alvo = _focusable(campo)
    if alvo is campo:
        return campo

    def passo(delta: int) -> Callable[[Any], str]:
        def mover(_evento: Any) -> str:
            valores = list(campo.cget("values") or [])
            if not valores:
                return "break"
            try:
                indice = valores.index(campo.get())
            except ValueError:
                indice = 0
            escolhido = valores[(indice + delta) % len(valores)]
            campo.set(escolhido)
            comando = campo.cget("command")
            if callable(comando):
                comando(escolhido)
            return "break"

        return mover

    def abrir(_evento: Any) -> str:
        try:
            campo._open_dropdown_menu()
        except Exception:  # pragma: no cover - interno do customtkinter
            pass
        return "break"

    _bind_keys(
        alvo,
        {
            "<Down>": passo(1),
            "<Up>": passo(-1),
            "<space>": abrir,
            "<Return>": abrir,
            "<Alt-Down>": abrir,
        },
    )
    return campo


def keyboard_toggle(caixa: Any) -> Any:
    """Torna um ``CTkCheckBox``/``CTkSwitch`` alcançável e alternável por teclado."""
    alvo = _focusable(caixa)
    if alvo is caixa:
        return caixa

    def alternar(_evento: Any) -> str:
        try:
            caixa.toggle()
        except Exception:  # pragma: no cover
            pass
        return "break"

    _bind_keys(alvo, {"<space>": alternar, "<Return>": alternar})
    return caixa


def set_field_error(widget: Any, message: str = "") -> None:
    """Marca o campo como invalido: borda de perigo + mensagem sob o campo."""
    estado = _field_state(widget)
    if estado is None:
        estado = _field_state(attach_field_states(widget))
    estado["error"] = True
    estado["warning"] = False
    estado["message"] = message
    _apply_field_state(widget)
    _update_hint(widget)


def set_field_warning(widget: Any, message: str = "") -> None:
    """Marca o campo como suspeito, sem impedir salvar (ex.: rodadas demais)."""
    estado = _field_state(widget)
    if estado is None:
        estado = _field_state(attach_field_states(widget))
    estado["warning"] = True
    estado["error"] = False
    estado["message"] = message
    _apply_field_state(widget)
    _update_hint(widget)


def clear_field_error(widget: Any) -> None:
    """Devolve o campo ao repouso (ou ao foco, se ele estiver focado)."""
    estado = _field_state(widget)
    if estado is None:
        return
    estado["error"] = False
    estado["warning"] = False
    estado["message"] = ""
    _apply_field_state(widget)
    _update_hint(widget)


def field_has_error(widget: Any) -> bool:
    """Se o campo esta marcado como invalido — usado por testes e por validacao."""
    estado = _field_state(widget)
    return bool(estado and estado["error"])


def text_field(master: Any, *, placeholder: str, **kwargs: Any) -> ctk.CTkEntry:
    """Campo de texto de uma linha. ``placeholder`` é obrigatório (P3-6):
    a dica de formato ("Ex.: 90'+30\"", "dd/mm/aaaa") faz parte da anatomia."""
    kwargs.setdefault("width", FIELD_MD)
    kwargs.setdefault("height", FIELD_HEIGHT)
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("font", font_field())
    return attach_field_states(ctk.CTkEntry(master, placeholder_text=placeholder, **kwargs))


def select_field(
    master: Any,
    *,
    values: list[str],
    command: Callable[[str], None] | None = None,
    variable: Any = None,
    **kwargs: Any,
) -> ctk.CTkOptionMenu:
    """Seleção com anatomia de CAMPO, não de botão (P3-5).

    O ``CTkOptionMenu`` padrão é um bloco preenchido com o accent — correto para
    ação, errado para dado: numa coluna de formulário ele alterna caixa clara /
    bloco de cor. Aqui o corpo usa o fundo de campo do tema, o texto usa a tinta
    de campo e o chevron fica na cor da borda; o dropdown segue o painel. As
    cores são os *tokens vivos* (mutados pelo preset), então o ``restyle``
    reaplica a troca de tema normalmente.
    """
    kwargs.setdefault("width", FIELD_MD)
    kwargs.setdefault("height", FIELD_HEIGHT)
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("font", font_field())
    kwargs.setdefault("fg_color", THEME_FIELD_BG)
    kwargs.setdefault("text_color", THEME_FIELD_TEXT)
    kwargs.setdefault("button_color", THEME_FIELD_BORDER)
    kwargs.setdefault("button_hover_color", THEME_ACCENT)
    kwargs.setdefault("dropdown_fg_color", THEME_PANEL_BG)
    kwargs.setdefault("dropdown_text_color", THEME_TEXT_MAIN)
    kwargs.setdefault("dropdown_hover_color", THEME_TREE_EVEN)
    return keyboard_select(
        attach_field_states(
            ctk.CTkOptionMenu(master, values=values, command=command, variable=variable, **kwargs)
        )
    )


def text_area(master: Any, *, height: int = 110, **kwargs: Any) -> ctk.CTkTextbox:
    """Texto multilinha. Nasce com borda de 1px (P3-5): o ``CTkTextbox`` de
    fábrica tem ``border_width=0`` e vira uma área invisível sobre o painel.
    Alturas em passos: 80 (curta), 110 (padrão), 200 (corpo de mensagem)."""
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("wrap", "word")
    kwargs.setdefault("font", font_field())
    return attach_field_states(ctk.CTkTextbox(master, height=height, **kwargs))


def date_field(master: Any, **kwargs: Any) -> Any:
    """Campo de data do app: ``MaskedDateEntry`` (máscara, clamp, calendário),
    dimensionado pela escala. Único campo de data permitido — nada de
    ``DateEntry`` nativo destoando do tema."""
    from ..support import MaskedDateEntry  # tardio: support importa components

    kwargs.setdefault("width", FIELD_SM)
    kwargs.setdefault("height", FIELD_HEIGHT)
    kwargs.setdefault("corner_radius", FIELD_RADIUS)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("font", font_field())
    return attach_field_states(MaskedDateEntry(master, **kwargs))


def labeled_field(
    master: Any,
    label: str,
    builder: Callable[[ctk.CTkFrame], Any],
    *,
    help_text: str = "",
    **kwargs: Any,
) -> tuple[ctk.CTkFrame, Any]:
    """Rótulo ACIMA do campo como unidade única (container transparente).

    ``builder`` recebe o container e devolve o campo (``text_field``,
    ``select_field``, ...). Devolve ``(container, campo)`` — a tela posiciona o
    container e guarda o campo. Fecha o espaçamento rótulo→campo em
    ``SPACE_XS``, que solto variava em mais de dez combinações de ``pady``.

    A **linha de mensagem** sob o campo é criada aqui e fica reservada mesmo
    vazia: é nela que ``set_field_error`` escreve. Reservar evita que o
    formulário inteiro pule para baixo quando o primeiro erro aparece — o
    salto é o que faz o usuário perder de vista o campo que errou.
    """
    box = ctk.CTkFrame(master, fg_color="transparent", **kwargs)
    box.grid_columnconfigure(0, weight=1)
    rotulo = ctk.CTkLabel(
        box, text=label, font=font_field_label(), text_color=THEME_TEXT_SUB, anchor="w"
    )
    rotulo.grid(row=0, column=0, sticky="w")
    campo = builder(box)
    campo.grid(row=1, column=0, sticky="ew", pady=(SPACE_XS, 0))
    hint = ctk.CTkLabel(
        box,
        text=help_text,
        font=ctk.CTkFont(size=SIZE_BODY - 1),
        text_color=THEME_TEXT_SUB,
        anchor="w",
        justify="left",
    )
    hint.grid(row=2, column=0, sticky="ew")
    estado = _field_state(campo) or _field_state(attach_field_states(campo))
    estado["hint"] = hint
    estado["help"] = help_text
    return box, campo
