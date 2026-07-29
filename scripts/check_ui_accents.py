"""Lint de acentuação nos textos visíveis da interface (F5.12 / P3-15).

A F3.5 corrigiu 93 rótulos e não deixou nada que impedisse a volta — e a
auditoria de 2026-07-29 achou ~26 palavras sem acento de novo, a começar pela
tela Início ("Inicio", "acao", "pendencia"). Um lint resolve; a pergunta era
qual regra ele aplica.

**A regra é a auto-consistência**, não um dicionário. O app é quem diz como se
escreve cada palavra: se "Classificação" aparece no catálogo e "Classificacao"
aparece numa tela, a segunda está errada — e isso vale sem manter lista de
palavras portuguesas, sem depender de biblioteca, e melhora sozinho a cada
texto novo escrito direito.

O corpus é o **texto que o usuário vê**: os valores do catálogo
(`i18n/pt_BR.json`) mais os literais passados a ``text=``, ``label=``,
``placeholder_text=``, ``help_text=`` e afins em ``src/ui``. Comentário e nome
de variável ficam de fora de propósito — o app é PT-BR na tela e ASCII no
código, e misturar as duas coisas faria o lint brigar com a convenção.

Uso:
    python scripts/check_ui_accents.py            # reprova o que estiver torto
    python scripts/check_ui_accents.py --lista    # so lista os suspeitos
"""
from __future__ import annotations

import ast
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"
CATALOGO = RAIZ / "i18n" / "pt_BR.json"

# Atributos cujo valor vai para a tela. `title=` entra porque e o titulo da
# janela; `tip=` porque o tooltip e texto tanto quanto o rotulo.
ATRIBUTOS_VISIVEIS = {
    "text",
    "label",
    "title",
    "placeholder_text",
    "help_text",
    "empty_title",
    "empty_description",
    "tip",
    "message",
    "busy_message",
    "confirm_text",
    "cancel_text",
    "close_text",
}

# Texto visivel tambem chega por argumento POSICIONAL, e foi por ai que a
# primeira versao deste lint deixou passar a tela de Configuracoes do app
# inteira: `_page_title("Configurações do aplicativo", "Ajuste preferencias
# locais...")` nao tem nenhum `text=`. Aqui ficam as funcoes de UI cujo
# posicional e texto — nome da funcao -> indices dos argumentos.
POSICIONAIS_VISIVEIS = {
    "_page_title": (0, 1),
    "_section_title": (1,),
    "primary_button": (1,),
    "secondary_button": (1,),
    "neutral_button": (1,),
    "danger_button": (1,),
    "section": (0,),
    "note": (0,),
    "text": (0,),
    "select": (0,),
    "date": (0,),
    "area": (0,),
    "field": (0,),
    "labeled_field": (1,),
    "_show_info": (0,),
    "_show_warning": (0,),
    "_show_error": (),  # recebe excecao, nao texto
    "_show_report": (0, 1),
    "_show_toast": (0,),
    "confirm_dialog": (1, 2),
    "alert_dialog": (1, 2),
    "tri_state_dialog": (1, 2),
    "report_dialog": (1, 2),
    "choice_dialog": (1, 2),
    "Dialog": (1,),
    "Tooltip": (1,),
    "modal": (1,),
    "close_button": (1,),
}

# Tabela de campos: `[("address", "Endereco"), ...]` — o rotulo so vira `text=`
# muitas linhas depois, dentro do laco que monta o formulario. Reconhecida pela
# forma: primeiro elemento com cara de CHAVE (`^[a-z][a-z0-9_]*$`) e segundo com
# cara de ROTULO (tem espaco ou comeca com maiuscula). Restrito assim de
# proposito: uma lista de nomes de icone ("calendario", "integracoes") nao passa
# no teste do rotulo, e o app e ASCII no codigo — o lint nao pode brigar com
# isso.
_CHAVE_DE_CAMPO = re.compile(r"^[a-z][a-z0-9_]*$")


def _parece_rotulo(texto: str) -> bool:
    return bool(texto) and (" " in texto or texto[0].isupper())


# Cabecalho de tabela chega como DICIONARIO (`{"action": "Acao"}`) no terceiro
# posicional do `_make_tree`. Sem isto, "Acao" e "Descricao" passavam batido —
# e cabecalho de coluna e dos textos mais lidos da tela.
DICIONARIOS_VISIVEIS = {"_make_tree": (2,)}

# Palavras em que **as duas grafias existem** em portugues, e por isso a
# auto-consistencia nao decide: "esta mesa" x "esta pronto", "eu publico" x
# "publico alvo". Cada entrada e uma decisao, nao uma isencao preguicosa.
HOMOGRAFOS = {
    "esta",  # demonstrativo x verbo estar
    "publico",  # verbo publicar x adjetivo/substantivo
    "continua",  # verbo continuar x adjetivo continua
    "duvida",  # verbo duvidar x substantivo duvida
    "pratica",  # verbo praticar x substantivo pratica
    "secretaria",  # cargo x lugar
    "sabia",  # verbo saber x adjetivo sabia
    "critica",  # verbo criticar x substantivo critica
    "analise",  # verbo analisar (imperativo) x substantivo analise
    "medico",  # raro, mas o par existe
    "fabrica",  # verbo fabricar x substantivo fabrica
}

_PALAVRA = re.compile(r"[A-Za-zÀ-ÿ]{4,}")

# `{codigo}` num texto do catalogo NAO e palavra visivel: e o **nome do
# parametro** que o `t(chave, codigo=...)` preenche. Acentuar ali quebra a
# chamada — e foi exatamente o que a primeira versao deste lint tentou fazer.
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def _visivel(texto: str) -> str:
    """O texto sem os campos de substituição — só o que o usuário lê."""
    return _PLACEHOLDER.sub(" ", texto)


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _textos_do_catalogo() -> list[tuple[str, str]]:
    """Valores do catálogo, **menos** as chaves de busca.

    ``nav.*.keywords`` não é texto que se lê: é o que o usuário **digita** no
    command palette. Escrever "classificacao" ali é o comportamento correto —
    quem procura sem acento tem de achar. Cobrar acento nessas chaves seria o
    lint brigando com o propósito delas.
    """
    if not CATALOGO.is_file():  # pragma: no cover - repo sem catalogo
        return []
    dados = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return [
        (f"i18n/pt_BR.json:{chave}", str(valor))
        for chave, valor in dados.items()
        if not chave.endswith(".keywords")
    ]


def _textos_do_codigo() -> list[tuple[str, str]]:
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(UI.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - arquivo em edicao
            continue
        nome = arquivo.relative_to(RAIZ).as_posix()
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            for palavra_chave in no.keywords:
                if palavra_chave.arg not in ATRIBUTOS_VISIVEIS:
                    continue
                valor = palavra_chave.value
                if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                    achados.append((f"{nome}:{valor.lineno}", valor.value))

            chamada = no.func.id if isinstance(no.func, ast.Name) else getattr(no.func, "attr", "")
            for indice in POSICIONAIS_VISIVEIS.get(chamada, ()):
                if indice >= len(no.args):
                    continue
                valor = no.args[indice]
                if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                    achados.append((f"{nome}:{valor.lineno}", valor.value))
            for indice in DICIONARIOS_VISIVEIS.get(chamada, ()):
                if indice >= len(no.args):
                    continue
                valor = no.args[indice]
                if not isinstance(valor, ast.Dict):
                    continue
                for item in valor.values:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        achados.append((f"{nome}:{item.lineno}", item.value))

        for no in ast.walk(arvore):
            if not isinstance(no, ast.Tuple) or len(no.elts) < 2:
                continue
            chave, rotulo = no.elts[0], no.elts[1]
            if not (isinstance(chave, ast.Constant) and isinstance(chave.value, str)):
                continue
            if not (isinstance(rotulo, ast.Constant) and isinstance(rotulo.value, str)):
                continue
            if _CHAVE_DE_CAMPO.match(chave.value) and _parece_rotulo(rotulo.value):
                achados.append((f"{nome}:{rotulo.lineno}", rotulo.value))
    return achados


def corpus() -> list[tuple[str, str]]:
    """``(origem, texto)`` de tudo que o usuário lê na interface."""
    return _textos_do_catalogo() + _textos_do_codigo()


def grafias_acentuadas(textos: list[tuple[str, str]]) -> dict[str, set[str]]:
    """Palavra sem acento → grafias **acentuadas** que o próprio app usa."""
    mapa: dict[str, set[str]] = {}
    for _origem, texto in textos:
        for palavra in _PALAVRA.findall(_visivel(texto)):
            if _sem_acento(palavra) != palavra:
                mapa.setdefault(_sem_acento(palavra).lower(), set()).add(palavra)
    return mapa


def checar_acentos() -> list[str]:
    """Palavras que o app escreve acentuadas em um lugar e sem acento em outro."""
    textos = corpus()
    acentuadas = grafias_acentuadas(textos)
    problemas: list[str] = []
    for origem, texto in textos:
        for palavra in _PALAVRA.findall(_visivel(texto)):
            chave = palavra.lower()
            if _sem_acento(palavra) != palavra or chave in HOMOGRAFOS:
                continue
            certas = acentuadas.get(chave)
            if not certas:
                continue
            problemas.append(
                f"{origem}: '{palavra}' sem acento — o app escreve "
                f"{sorted(certas)} em outro lugar (P3-15/F5.12)."
            )
    return problemas


def main() -> int:
    textos = corpus()
    if "--lista" in sys.argv:
        acentuadas = grafias_acentuadas(textos)
        suspeitas = sorted(
            {
                palavra
                for _origem, texto in textos
                for palavra in _PALAVRA.findall(_visivel(texto))
                if _sem_acento(palavra) == palavra
                and palavra.lower() in acentuadas
                and palavra.lower() not in HOMOGRAFOS
            }
        )
        for palavra in suspeitas:
            print(f"{palavra} -> {sorted(acentuadas[palavra.lower()])}")
        return 0

    problemas = checar_acentos()
    if problemas:
        print("Acentuacao de textos visiveis:\n")
        for problema in problemas:
            print(f"  {problema}")
        print(f"\n{len(problemas)} ocorrencia(s).")
        return 1
    print(f"Acentuacao OK ({len(textos)} textos visiveis conferidos).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
